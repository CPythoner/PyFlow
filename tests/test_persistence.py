import tempfile
import unittest
from pathlib import Path

from pyflow_app.persistence import export_flows_config, load_flows_config, load_json_file, save_flows_to_file
from pyflow_app.sample_flow import build_sample_flow_manager


class PersistenceTests(unittest.TestCase):
    def test_save_and_load_flows_file_round_trip(self):
        manager = build_sample_flow_manager()
        flows = {manager.flow_id: manager}
        flow_order = [manager.flow_id]

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "flows.json"
            save_flows_to_file(str(file_path), flows, flow_order, manager.flow_id, "light")
            payload = load_json_file(str(file_path))

        loaded = load_flows_config(payload)

        self.assertEqual(loaded.current_flow_id, manager.flow_id)
        self.assertEqual(loaded.theme_name, "light")
        self.assertEqual(loaded.flow_order, [manager.flow_id])
        self.assertEqual(loaded.flows[manager.flow_id].flow_name, manager.flow_name)

    def test_load_flows_config_supports_legacy_single_flow_shape(self):
        legacy_payload = {
            "id": "legacy",
            "name": "Legacy Flow",
            "nodes": [
                {
                    "id": "only",
                    "name": "Only Node",
                    "commands": [{"name": "run", "command": "echo ok"}],
                }
            ],
            "connections": [],
        }

        loaded = load_flows_config(legacy_payload)

        self.assertEqual(loaded.current_flow_id, "legacy")
        self.assertEqual(loaded.flow_order, ["legacy"])
        self.assertEqual(loaded.flows["legacy"].nodes["only"].name, "Only Node")

    def test_export_flows_config_contains_theme_and_current_flow(self):
        manager = build_sample_flow_manager()
        payload = export_flows_config({manager.flow_id: manager}, [manager.flow_id], manager.flow_id, "dark")

        self.assertEqual(payload["current_flow_id"], manager.flow_id)
        self.assertEqual(payload["theme"], "dark")
        self.assertEqual(payload["flows"][0]["id"], manager.flow_id)


if __name__ == "__main__":
    unittest.main()
