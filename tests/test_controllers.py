import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from pyflow_app.controllers import ExecutionController, FlowEditController
from pyflow_app.models import Command, TaskFlowManager


class FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)


class FakeWorker:
    def __init__(self, task_manager, node_ids, respect_skip=True, route_by_connections=False):
        self.task_manager = task_manager
        self.node_ids = node_ids
        self.respect_skip = respect_skip
        self.route_by_connections = route_by_connections
        self.node_started = FakeSignal()
        self.node_finished = FakeSignal()
        self.command_executing = FakeSignal()
        self.command_finished = FakeSignal()
        self.log_message = FakeSignal()
        self.output_message = FakeSignal()
        self.all_finished = FakeSignal()
        self.finished = FakeSignal()
        self.stopped = FakeSignal()
        self.started = False
        self.stop_requested = False
        self.running = True

    def isRunning(self):
        return self.running

    def start(self):
        self.started = True

    def request_stop(self):
        self.stop_requested = True


class ExecutionControllerTests(unittest.TestCase):
    def test_execution_controller_starts_and_stops_worker(self):
        manager = TaskFlowManager()
        manager.add_node("a", "A")

        with patch("pyflow_app.controllers.ExecuteWorker", FakeWorker):
            controller = ExecutionController()
            controller.start(manager, ["a"], respect_skip=False, route_by_connections=True)

            self.assertTrue(controller.is_running())
            self.assertEqual(controller.worker.node_ids, ["a"])
            self.assertFalse(controller.worker.respect_skip)
            self.assertTrue(controller.worker.route_by_connections)

            controller.stop()
            self.assertTrue(controller.worker.stop_requested)

            controller._on_worker_stopped()
            self.assertTrue(controller.execution_was_stopped)

            controller._on_worker_finished()
            self.assertFalse(controller.is_running())


class FlowEditControllerTests(unittest.TestCase):
    def setUp(self):
        self.manager = TaskFlowManager()
        self.manager.add_node("a", "A")
        self.manager.add_node("b", "B")
        self.manager.add_node("c", "C")
        self.selected_node_id = "a"
        self.controller = FlowEditController(lambda: self.manager, lambda: self.selected_node_id)

    def test_connect_nodes_insert_into_chain_rewires_successor(self):
        self.controller.connect_nodes("a", "b", insert_into_chain=False)
        self.controller.connect_nodes("a", "c", insert_into_chain=True)

        self.assertIsNotNone(self.manager.find_connection("a", "c", "success"))
        self.assertIsNotNone(self.manager.find_connection("c", "b", "success"))
        self.assertIsNone(self.manager.find_connection("a", "b", "success"))

    def test_add_copy_delete_node_flow(self):
        node = self.controller.add_node(
            {
                "node_id": "d",
                "name": "D",
                "icon": "📦",
                "description": "desc",
                "working_dir": "",
                "terminal_type": "bash",
                "continue_on_error": True,
                "connect_after_selected": True,
                "commands": [{"name": "run", "command": "echo ok"}],
            },
            {"x": 10.0, "y": 20.0},
        )
        self.assertEqual(node.id, "d")
        self.assertIsNotNone(self.manager.find_connection("a", "d", "success"))

        self.selected_node_id = "d"
        copied = self.controller.copy_selected_node(lambda: {"x": 0.0, "y": 0.0})
        self.assertIsNotNone(copied)
        self.assertNotEqual(copied.id, "d")
        self.assertEqual(copied.commands[0].command, "echo ok")

        deleted = self.controller.delete_selected_node()
        self.assertTrue(deleted)
        self.assertNotIn("d", self.manager.nodes)

    def test_update_connection_condition_rejects_duplicate(self):
        self.controller.connect_nodes("a", "b", condition="success")
        self.controller.connect_nodes("a", "b", condition="failed")

        changed = self.controller.update_connection_condition("a", "b", "failed", "success")
        self.assertFalse(changed)


if __name__ == "__main__":
    QApplication.instance() or QApplication([])
    unittest.main()
