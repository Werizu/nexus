"""NEXUS Agent — Windows Service wrapper."""

import sys
import os
from pathlib import Path

# Add agent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
except ImportError:
    print("pywin32 is required. Install with: pip install pywin32")
    sys.exit(1)

from nexus_agent import NexusAgent, load_config


class NexusAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NexusAgent"
    _svc_display_name_ = "NEXUS Agent"
    _svc_description_ = "NEXUS Smart Home Agent — connects this PC to the NEXUS Brain"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.agent = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.agent:
            self.agent.stop()

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        os.chdir(str(Path(__file__).parent))
        config = load_config()
        self.agent = NexusAgent(config)
        self.agent.start()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(NexusAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(NexusAgentService)
