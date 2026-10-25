import os
import sys

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

os.environ["MAA_AGENT_MODE"] = "1"

import my_action
import my_reco
import schedule_helper
import bounty_helper


def main():
    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)

    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
