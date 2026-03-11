import unittest

from pyflow_app.sample_flow import build_sample_flow_manager


class SampleFlowTests(unittest.TestCase):
    def test_sample_flow_contains_expected_chain(self):
        manager = build_sample_flow_manager()

        self.assertEqual(manager.flow_id, "sample_flow")
        self.assertEqual(manager.flow_name, "示例流程")
        self.assertEqual(manager.node_order, ["get_reviews", "kmeans", "clusters_list", "agent", "gsheets"])
        self.assertEqual(
            [(conn.from_id, conn.to_id) for conn in manager.connections],
            [
                ("get_reviews", "kmeans"),
                ("kmeans", "clusters_list"),
                ("clusters_list", "agent"),
                ("agent", "gsheets"),
            ],
        )

    def test_sample_flow_nodes_have_commands(self):
        manager = build_sample_flow_manager()
        self.assertTrue(all(manager.nodes[node_id].commands for node_id in manager.node_order))


if __name__ == "__main__":
    unittest.main()
