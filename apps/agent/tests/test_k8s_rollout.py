import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.metrics.k8s_rollout import _container_image, fetch_workload_rollout_info


class TestK8sRollout(unittest.TestCase):
    def test_container_image_prefers_named_container(self):
        container = MagicMock()
        container.name = "app"
        container.image = "repo/app:v1"
        other = MagicMock()
        other.name = "sidecar"
        other.image = "repo/sidecar:v1"
        replica_set = MagicMock()
        replica_set.spec.template.spec.containers = [other, container]
        self.assertEqual(_container_image(replica_set, "app"), "repo/app:v1")

    @patch("services.metrics.k8s_rollout._ensure_k8s_clients")
    def test_fetch_includes_current_and_previous_image(self, mock_clients):
        core_v1 = MagicMock()
        apps_v1 = MagicMock()
        mock_clients.return_value = (core_v1, apps_v1)

        dep_owner = MagicMock()
        dep_owner.kind = "Deployment"
        dep_owner.name = "app"
        rs_owner = MagicMock()
        rs_owner.kind = "ReplicaSet"
        rs_owner.name = "app-rs-new"

        pod = MagicMock()
        pod.metadata.owner_references = [rs_owner]
        core_v1.read_namespaced_pod.return_value = pod

        current_container = MagicMock()
        current_container.name = "app"
        current_container.image = "repo/app:v2"
        current_rs = MagicMock()
        current_rs.metadata.name = "app-rs-new"
        current_rs.metadata.creation_timestamp = datetime(2026, 6, 25, 4, 36, tzinfo=timezone.utc)
        current_rs.metadata.owner_references = [dep_owner]
        current_rs.spec.template.spec.containers = [current_container]

        prev_container = MagicMock()
        prev_container.name = "app"
        prev_container.image = "repo/app:v1"
        previous_rs = MagicMock()
        previous_rs.metadata.name = "app-rs-old"
        previous_rs.metadata.creation_timestamp = datetime(2026, 6, 20, 4, 36, tzinfo=timezone.utc)
        previous_rs.metadata.owner_references = [dep_owner]
        previous_rs.spec.template.spec.containers = [prev_container]

        apps_v1.read_namespaced_replica_set.return_value = current_rs
        apps_v1.read_namespaced_deployment.return_value = MagicMock(status=MagicMock(conditions=[]))
        apps_v1.list_namespaced_replica_set.return_value = MagicMock(items=[current_rs, previous_rs])

        result = fetch_workload_rollout_info("ns", "pod-1", container="app")
        self.assertEqual(result["current_image"], "repo/app:v2")
        self.assertEqual(result["previous_image"], "repo/app:v1")
        self.assertEqual(result["previous_replicaset"], "app-rs-old")
        self.assertTrue(result["image_changed"])


if __name__ == "__main__":
    unittest.main()
