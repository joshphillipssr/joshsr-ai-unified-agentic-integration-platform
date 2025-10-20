import React from "react";
import { Box, Text } from "ink";

export function Banner() {
  return (
    <Box flexDirection="column" marginBottom={1}>
      <Box>
        <Text bold color="cyan">
          ╔══════════════════════════════════════════════════════════════════════════════╗
        </Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
          __  __  ___  ___     ___         _     _
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
          |  \/  |/ __|/ _ \   | _ \___ __(_)___| |_ _ _ _  _
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
          | |\/| | (__| (_) |  |   / -_) _| (_-&lt;  _| '_| || |
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
          |_|  |_|\___|\___/   |_|_\___\__|_/__/\__|_|  \_, |
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
           /_\  ___ ___ (_)__| |_ __ _ _ _| |_         |__/
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
          / _ \(_-&lt;(_-&lt; | (_-&lt;  _/ _` | ' \  _|
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">║  </Text>
        <Text bold color="white">
         /_/ \_/__//__/_|/__/\__\__,_|_||_\__|
        </Text>
        <Text bold color="cyan">  ║</Text>
      </Box>
      <Box>
        <Text bold color="cyan">
          ╚══════════════════════════════════════════════════════════════════════════════╝
        </Text>
      </Box>
    </Box>
  );
}
