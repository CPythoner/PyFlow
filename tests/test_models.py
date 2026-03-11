import tempfile
import unittest
from pathlib import Path

from pyflow_app.models import Command, TaskFlowManager


class TaskFlowManagerTests(unittest.TestCase):
    def test_execution_order_follows_topology(self):
        manager = TaskFlowManager()
        manager.add_node("a", "A")
        manager.add_node("b", "B")
        manager.add_node("c", "C")
        manager.connect_nodes("a", "b")
        manager.connect_nodes("b", "c")

        self.assertEqual(manager.get_execution_order(), ["a", "b", "c"])

    def test_validate_flow_reports_duplicate_condition_branch(self):
        manager = TaskFlowManager()
        node_a = manager.add_node("a", "A")
        node_b = manager.add_node("b", "B")
        node_c = manager.add_node("c", "C")

        with tempfile.TemporaryDirectory() as temp_dir:
            for node in (node_a, node_b, node_c):
                node.commands.append(Command(name="run", command="echo ok"))
                node.working_dir = temp_dir

            manager.connect_nodes("a", "b", "success")
            manager.connect_nodes("a", "c", "success")

            errors = manager.validate_flow()

        self.assertTrue(any("多条“成功后”连线" in error for error in errors))

    def test_manager_round_trip_preserves_flow_metadata(self):
        manager = TaskFlowManager()
        manager.flow_id = "demo"
        manager.flow_name = "Demo"
        node = manager.add_node("build", "Build", "⚙️")
        node.description = "Run build"
        node.commands.append(Command(name="compile", command="python -m py_compile pyflow.py"))

        copied = TaskFlowManager()
        copied.load_from_dict(manager.to_dict(include_flow_meta=True))

        self.assertEqual(copied.flow_id, "demo")
        self.assertEqual(copied.flow_name, "Demo")
        self.assertEqual(copied.node_order, ["build"])
        self.assertEqual(copied.nodes["build"].commands[0].command, "python -m py_compile pyflow.py")


if __name__ == "__main__":
    unittest.main()
