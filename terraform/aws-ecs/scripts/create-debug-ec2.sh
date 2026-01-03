#!/bin/bash

# Script to create an EC2 instance for DocumentDB debugging
# This instance will be in the same VPC as the ECS cluster

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"

AWS_REGION="${AWS_REGION:-us-east-1}"

echo "=========================================="
echo "Creating EC2 Debug Instance for DocumentDB"
echo "=========================================="
echo ""

# Check if terraform outputs exist
if [ ! -f "$TERRAFORM_DIR/terraform.tfstate" ]; then
    echo "ERROR: terraform.tfstate not found in $TERRAFORM_DIR"
    echo "Please run 'terraform apply' first"
    exit 1
fi

# Get terraform outputs
echo "Reading Terraform outputs..."
cd "$TERRAFORM_DIR"
VPC_ID=$(terraform output -json | jq -r '.vpc_id.value')
PRIVATE_SUBNETS=$(terraform output -json | jq -r '.private_subnet_ids.value[0]')
PUBLIC_SUBNETS=$(terraform output -json | jq -r '.public_subnet_ids.value[0]')
DOCUMENTDB_ENDPOINT=$(terraform output -json | jq -r '.documentdb_cluster_endpoint.value')
DOCUMENTDB_SG=$(terraform output -json | jq -r '.documentdb_security_group_id.value')
ECS_CLUSTER=$(terraform output -json | jq -r '.ecs_cluster_name.value')

echo "Configuration:"
echo "  Region: $AWS_REGION"
echo "  VPC: $VPC_ID"
echo "  Public Subnet: $PUBLIC_SUBNETS"
echo "  DocumentDB Endpoint: $DOCUMENTDB_ENDPOINT"
echo "  DocumentDB Security Group: $DOCUMENTDB_SG"
echo ""

# Check if key pair exists or prompt
if [ -z "$SSH_KEY_NAME" ]; then
    echo "Available key pairs:"
    aws ec2 describe-key-pairs --region "$AWS_REGION" --query 'KeyPairs[*].KeyName' --output table
    echo ""
    echo "ERROR: SSH key name not provided"
    echo "Please set SSH_KEY_NAME environment variable:"
    echo "  export SSH_KEY_NAME=your-key-name"
    echo "  $0"
    exit 1
fi

echo "  SSH Key: $SSH_KEY_NAME"
echo ""

# Get Ubuntu 24.04 LTS AMI
echo "Finding latest Ubuntu 24.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
              "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text \
    --region "$AWS_REGION")

echo "  AMI: $AMI_ID (Ubuntu 24.04)"
echo ""

# Get current IP
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "  Your IP: $MY_IP"
echo ""

# Create security group for the debug instance
echo "Creating security group for debug instance..."
SG_NAME="documentdb-debug-instance"
SG_DESCRIPTION="Security group for DocumentDB debug EC2 instance"

# Check if security group already exists
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "None")

if [ "$EXISTING_SG" != "None" ] && [ -n "$EXISTING_SG" ]; then
    echo "Using existing security group: $EXISTING_SG"
    DEBUG_SG_ID="$EXISTING_SG"
else
    DEBUG_SG_ID=$(aws ec2 create-security-group \
        --group-name "$SG_NAME" \
        --description "$SG_DESCRIPTION" \
        --vpc-id "$VPC_ID" \
        --region "$AWS_REGION" \
        --query 'GroupId' \
        --output text)

    echo "Created security group: $DEBUG_SG_ID"

    # Allow RDP (3389) from your IP
    echo "Adding RDP rule (port 3389) from $MY_IP..."
    aws ec2 authorize-security-group-ingress \
        --group-id "$DEBUG_SG_ID" \
        --protocol tcp \
        --port 3389 \
        --cidr "$MY_IP/32" \
        --region "$AWS_REGION" 2>/dev/null || echo "  (rule may already exist)"

    # Allow SSH (22) from your IP
    echo "Adding SSH rule (port 22) from $MY_IP..."
    aws ec2 authorize-security-group-ingress \
        --group-id "$DEBUG_SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr "$MY_IP/32" \
        --region "$AWS_REGION" 2>/dev/null || echo "  (rule may already exist)"
fi

echo "Security Group ID: $DEBUG_SG_ID"
echo ""

# Update DocumentDB security group to allow traffic from debug instance
echo "Updating DocumentDB security group to allow access from debug instance..."
aws ec2 authorize-security-group-ingress \
    --group-id "$DOCUMENTDB_SG" \
    --protocol tcp \
    --port 27017 \
    --source-group "$DEBUG_SG_ID" \
    --region "$AWS_REGION" 2>/dev/null || echo "  (rule may already exist)"

# Create user data script
read -r -d '' USER_DATA <<'EOF' || true
#!/bin/bash
set -e

# Update system
apt-get update
apt-get upgrade -y

# Install XFCE desktop and XRDP
apt-get install -y xfce4 xfce4-goodies xrdp

# Configure XRDP to use XFCE
echo "xfce4-session" > /home/ubuntu/.xsession
chown ubuntu:ubuntu /home/ubuntu/.xsession

# Enable and start XRDP
systemctl enable xrdp
systemctl start xrdp

# Install Firefox and useful tools
apt-get install -y firefox curl wget vim git jq

# Install Python and MongoDB tools
apt-get install -y python3-pip python3-venv
pip3 install motor pymongo dnspython --break-system-packages

# Download DocumentDB CA bundle
wget https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -O /home/ubuntu/global-bundle.pem
chown ubuntu:ubuntu /home/ubuntu/global-bundle.pem

# Set password for ubuntu user
echo "ubuntu:DocumentDB2025!" | chpasswd

# Create debug script on desktop
mkdir -p /home/ubuntu/Desktop
cat > /home/ubuntu/debug-scopes.py <<'EOFPYTHON'
#!/usr/bin/env python3
import asyncio
import json
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def debug_scopes():
    host = os.getenv("DOCUMENTDB_HOST", "DOCUMENTDB_ENDPOINT_PLACEHOLDER")
    port = 27017
    database = "mcp_registry"
    namespace = "default"
    ca_file = "/home/ubuntu/global-bundle.pem"

    connection_string = f"mongodb://{host}:{port}/{database}"
    client = AsyncIOMotorClient(connection_string, retryWrites=False, tls=True, tlsCAFile=ca_file)
    db = client[database]

    try:
        server_info = await client.server_info()
        print(f"Connected to DocumentDB version: {server_info.get('version')}")
        print()

        collection_name = f"mcp_scopes_{namespace}"
        collection = db[collection_name]

        count = await collection.count_documents({})
        print(f"Collection: {collection_name}")
        print(f"Document count: {count}")
        print()

        if count == 0:
            print("WARNING: No scope documents found!")
            print()
            collections = await db.list_collection_names()
            print("Available collections:")
            for coll in sorted(collections):
                print(f"  - {coll}")
        else:
            print("Scope documents:")
            print("-" * 80)
            cursor = collection.find({})
            async for doc in cursor:
                scope_id = doc.get("_id", "unknown")
                server_access = doc.get("server_access", [])
                group_mappings = doc.get("group_mappings", [])

                print(f"\nScope ID: {scope_id}")
                print(f"  Group Mappings: {group_mappings}")
                print(f"  Server Access: {len(server_access)} rules")
                if server_access:
                    for rule in server_access:
                        print(f"    {json.dumps(rule)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_scopes())
EOFPYTHON

sed -i "s/DOCUMENTDB_ENDPOINT_PLACEHOLDER/DOCUMENTDB_ENDPOINT_VALUE/g" /home/ubuntu/debug-scopes.py
chmod +x /home/ubuntu/debug-scopes.py
chown ubuntu:ubuntu /home/ubuntu/debug-scopes.py

# Create README on desktop
cat > /home/ubuntu/Desktop/README.txt <<'EOFREADME'
DocumentDB Debug Instance
=========================

This instance can access DocumentDB at:
- Host: DOCUMENTDB_ENDPOINT_VALUE
- Port: 27017
- Database: mcp_registry

To inspect scopes:
1. Open Terminal
2. Run: python3 /home/ubuntu/debug-scopes.py

CA Bundle: /home/ubuntu/global-bundle.pem

Default RDP password: DocumentDB2025!
PLEASE CHANGE THIS: sudo passwd ubuntu
EOFREADME

sed -i "s/DOCUMENTDB_ENDPOINT_VALUE/DOCUMENTDB_ENDPOINT_ACTUAL/g" /home/ubuntu/Desktop/README.txt
chown ubuntu:ubuntu /home/ubuntu/Desktop/README.txt

echo "Setup complete!"
EOF

# Replace placeholder with actual DocumentDB endpoint in user data
USER_DATA="${USER_DATA//DOCUMENTDB_ENDPOINT_VALUE/$DOCUMENTDB_ENDPOINT}"
USER_DATA="${USER_DATA//DOCUMENTDB_ENDPOINT_ACTUAL/$DOCUMENTDB_ENDPOINT}"

# Launch instance
echo "Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "t3.medium" \
    --key-name "$SSH_KEY_NAME" \
    --subnet-id "$PUBLIC_SUBNETS" \
    --security-group-ids "$DEBUG_SG_ID" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=documentdb-debug},{Key=Purpose,Value=DocumentDB-Debugging},{Key=ManagedBy,Value=Script}]" \
    --associate-public-ip-address \
    --region "$AWS_REGION" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance ID: $INSTANCE_ID"
echo ""
echo "Waiting for instance to start..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"

# Get instance details
INSTANCE_INFO=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].[PublicIpAddress,PrivateIpAddress]' \
    --output text)

PUBLIC_IP=$(echo "$INSTANCE_INFO" | awk '{print $1}')
PRIVATE_IP=$(echo "$INSTANCE_INFO" | awk '{print $2}')

echo ""
echo "=========================================="
echo "EC2 Instance Created Successfully!"
echo "=========================================="
echo ""
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "Private IP: $PRIVATE_IP"
echo ""
echo "XRDP is being installed (takes ~5 minutes)..."
echo ""
echo "To connect via RDP (after setup completes):"
echo "  1. Open Remote Desktop Connection on Windows"
echo "  2. Computer: $PUBLIC_IP:3389"
echo "  3. Username: ubuntu"
echo "  4. Password: DocumentDB2025!"
echo "  5. IMPORTANT: Change the password after first login!"
echo ""
echo "To connect via SSH:"
echo "  ssh -i ~/.ssh/$SSH_KEY_NAME.pem ubuntu@$PUBLIC_IP"
echo ""
echo "DocumentDB access:"
echo "  Host: $DOCUMENTDB_ENDPOINT"
echo "  Port: 27017"
echo "  Database: mcp_registry"
echo ""
echo "To run the debug script:"
echo "  python3 /home/ubuntu/debug-scopes.py"
echo ""
echo "To monitor installation progress:"
echo "  ssh -i ~/.ssh/$SSH_KEY_NAME.pem ubuntu@$PUBLIC_IP 'tail -f /var/log/cloud-init-output.log'"
echo ""
echo "To terminate this instance when done:"
echo "  aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $AWS_REGION"
echo ""
