import random

try:
    import obd
except Exception:
    obd = None


class OBDService:
    def __init__(self, port="COM5", demo_mode=False):
        self.port = port
        self.demo_mode = demo_mode
        self.connection = None

        if obd is None:
            self.demo_mode = True
            return

        try:
            self.connection = obd.OBD(
                port,
                fast=False,
                timeout=5
            )

            if not self.connection.is_connected():
                self.demo_mode = True

        except Exception:
            self.connection = None
            self.demo_mode = True

    def is_connected(self):
        if self.demo_mode:
            return False

        try:
            return self.connection is not None and self.connection.is_connected()
        except Exception:
            return False

    def _clean_value(self, value):
        try:
            text = str(value)

            text = text.replace("revolutions_per_minute", "")
            text = text.replace("kilometer_per_hour", "")
            text = text.replace("degree_Celsius", "")
            text = text.replace("percent", "")
            text = text.replace(" ", "")

            return text

        except Exception:
            return "N/A"

    def _query_value(self, command, fallback="N/A"):
        if not self.is_connected():
            return fallback

        try:
            response = self.connection.query(command)

            if response and response.value is not None:
                return self._clean_value(response.value)

            return fallback

        except Exception:
            return fallback

    def get_basic_data(self):
        if self.demo_mode or not self.is_connected():
            return self.get_demo_data()

        return {
            "speed": self._query_value(
                obd.commands.SPEED,
                "0"
            ),

            "rpm": self._query_value(
                obd.commands.RPM,
                "820"
            ),

            "coolant_temp": self._query_value(
                obd.commands.COOLANT_TEMP,
                "91"
            ),

            "throttle": self._query_value(
                obd.commands.THROTTLE_POS,
                "18"
            ),

            "engine_load": self._query_value(
                obd.commands.ENGINE_LOAD,
                "21"
            ),

            "fuel_level": self._query_value(
                obd.commands.FUEL_LEVEL,
                "82"
            )
        }

    def get_dtc_codes(self):
        if self.demo_mode or not self.is_connected():
            return [
                "P0301",
                "P0171"
            ]

        try:
            response = self.connection.query(
                obd.commands.GET_DTC
            )

            if response and response.value:
                return [
                    code[0] for code in response.value
                ]

            return []

        except Exception:
            return []

    def clear_dtc_codes(self):
        if self.demo_mode or not self.is_connected():
            return False

        try:
            response = self.connection.query(
                obd.commands.CLEAR_DTC
            )

            return response is not None

        except Exception:
            return False

    def get_connection_status(self):
        return {
            "connected": self.is_connected(),
            "demo_mode": self.demo_mode,
            "port": self.port
        }

    def get_demo_data(self):
        rpm = random.randint(780, 920)
        coolant = random.randint(88, 96)
        load = random.randint(16, 28)
        throttle = random.randint(10, 24)

        return {
            "speed": 0,
            "rpm": rpm,
            "coolant_temp": coolant,
            "throttle": throttle,
            "engine_load": load,
            "fuel_level": 82
        }