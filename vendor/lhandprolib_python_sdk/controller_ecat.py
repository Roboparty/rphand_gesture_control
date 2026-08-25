"""EtherCAT controller implementation."""

import threading
import time
from typing import Optional

from .controller_base import BaseLHandProController
from .lhandprolib_wrapper import LCN_ECAT


class EtherCATController(BaseLHandProController):
    def __init__(self, **kwargs):
        kwargs.pop("communication_mode", None)
        super().__init__(communication_mode="ECAT", **kwargs)
        self.ec_master = None
        self.stop_flag = None
        self.monitor_thread = None

    def _ec_send_callback(self, data: bytes) -> bool:
        if self.ec_master:
            return self.ec_master.setOutputs(data, len(data))
        print("EC master not initialized")
        return False

    def _monitor_thread_func(self) -> None:
        while not self.stop_flag.is_set() and self.is_connected:
            if self.ec_master:
                input_size = self.ec_master.getInputSize()
                inputs = self.ec_master.getInputs(input_size)
                if inputs is not None and self.sdk_handle:
                    self.sdk_handle.set_tpdo_data_decode(inputs)
            time.sleep(0.01)

    def _connect_transport(
        self,
        enable_motors: bool,
        home_motors: bool,
        home_wait_time: float,
        device_index: Optional[int],
        auto_select: bool,
        canfd_nom_baudrate: int,
        canfd_dat_baudrate: int,
        rs485_port_name: Optional[str],
        canfd_driver: Optional[str] = None,
    ) -> bool:
        from ethercat_master import EthercatMaster

        self.ec_master = EthercatMaster()
        print("Using EtherCAT communication (100M)")

        names = self.ec_master.scanNetworkInterfaces()
        print(f"Found network interfaces: {len(names)}")
        if len(names) == 0:
            print("No network interface found")
            self.ec_master = None
            return False

        channel_index = device_index
        if channel_index is None:
            if len(names) == 1 or auto_select:
                channel_index = 0
                print(f"Auto selected network interface: {names[channel_index]}")
            else:
                print(f"Select interface [0 - {len(names) - 1}]")
                for index, name in enumerate(names):
                    print(f"  [{index}] {name}")
                while True:
                    try:
                        user_input = input(">>> ").strip()
                        channel_index = 0 if user_input == "" else int(user_input)
                        if 0 <= channel_index < len(names):
                            break
                    except ValueError:
                        pass
                    print(f"Please enter a number in [0 - {len(names) - 1}]")
        elif not 0 <= channel_index < len(names):
            print(f"Invalid network interface index: {channel_index}")
            self.ec_master = None
            return False

        if not self.ec_master.init(channel_index, names):
            print("EtherCAT initialization failed")
            self.ec_master = None
            return False

        self.is_connected = True
        if not self.ec_master.start():
            print("EtherCAT start failed")
            self._cleanup_communication_resources()
            return False

        self.ec_master.run()
        self.sdk_handle.set_send_rpdo_callback(self._ec_send_callback)

        self.stop_flag = threading.Event()
        self.monitor_thread = threading.Thread(
            target=self._monitor_thread_func, daemon=True
        )
        self.monitor_thread.start()

        self.sdk_handle.initial(LCN_ECAT)
        return self._common_initialization(enable_motors, home_motors, home_wait_time)

    def _cleanup_communication_resources(self) -> None:
        if self.stop_flag:
            self.stop_flag.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        self.monitor_thread = None
        self.stop_flag = None
        if self.ec_master:
            try:
                self.ec_master.stop()
                time.sleep(0.1)
            finally:
                self.ec_master = None
