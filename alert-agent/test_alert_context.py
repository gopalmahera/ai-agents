import json
import unittest
from pathlib import Path

from alert_context import alert_for_prompt, build_alert_context


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample"


def _alert(labels: dict, annotations: dict | None = None) -> dict:
    return {
        "status": "firing",
        "labels": labels,
        "annotations": annotations or {},
    }


class TestPodRestartMskClassification(unittest.TestCase):
    def test_vitalsstream_full_labels(self):
        alert = _alert(
            {
                "alertname": "pod.restart.vitalsstream",
                "severity": "critical",
                "namespace": "msk",
                "job": "msk-kb",
                "topic": "wss.vitalsstream",
                "groupId": "group.wss.vitalsstream",
            },
            {
                "summary": "Topic Lag on wss.vitalsstream",
                "description": "Consumer Lag on group.wss.vitalsstream > 1000",
            },
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kafka")
        self.assertIsNone(ctx.namespace)
        self.assertIsNone(ctx.pod)
        self.assertEqual(ctx.topic, "wss.vitalsstream")
        self.assertEqual(ctx.group_id, "group.wss.vitalsstream")
        self.assertEqual(ctx.msk_job, "msk-kb")
        self.assertEqual(ctx.workload_namespace, "dozeeplatform")
        self.assertEqual(ctx.workload_deployment, "vitalswss")

    def test_vitalsstream_sparse_labels_from_annotations(self):
        alert = _alert(
            {
                "alertname": "pod.restart.vitalsstream",
                "severity": "critical",
                "namespace": "msk",
            },
            {
                "summary": "Topic Lag on wss.vitalsstream",
                "description": "Consumer Lag on group.wss.vitalsstream > 1000",
            },
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kafka")
        self.assertEqual(ctx.topic, "wss.vitalsstream")
        self.assertEqual(ctx.group_id, "group.wss.vitalsstream")
        self.assertEqual(ctx.msk_job, "msk-kb")

    def test_ecgstream_mapping(self):
        alert = _alert(
            {
                "alertname": "pod.restart.ecgstream",
                "severity": "critical",
                "namespace": "msk",
            },
            {
                "summary": "Topic Lag on misc.ecgstream",
                "description": "Consumer Lag on group.misc.ecgstream > 1000",
            },
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kafka")
        self.assertEqual(ctx.topic, "misc.ecgstream")
        self.assertEqual(ctx.group_id, "group.misc.ecgstream")
        self.assertEqual(ctx.workload_deployment, "sse")

    def test_vitals_kims_mapping(self):
        alert = _alert(
            {
                "alertname": "pod.restart.vitals.kims",
                "severity": "critical",
                "namespace": "msk",
            },
            {
                "summary": "Topic Lag on wss.vitalsstream",
                "description": "Consumer Lag on group.wss.vitals.kims > 1000",
            },
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kafka")
        self.assertEqual(ctx.topic, "wss.vitalsstream")
        self.assertEqual(ctx.group_id, "group.wss.vitals.kims")
        self.assertEqual(ctx.workload_deployment, "kimsvitalsint")

    def test_real_kubernetes_pod_restart_not_kafka(self):
        alert = _alert(
            {
                "alertname": "PodRestarting",
                "severity": "warning",
                "namespace": "production",
                "pod": "api-server-7f8c9d",
            }
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kubernetes")
        self.assertEqual(ctx.namespace, "production")
        self.assertEqual(ctx.pod, "api-server-7f8c9d")

    def test_msk_dot_alertname_still_kafka(self):
        alert = _alert(
            {
                "alertname": "msk.kb.wss.vitalsstream > 3000",
                "severity": "warning",
                "job": "msk-kb",
                "topic": "wss.vitalsstream",
                "groupId": "group.wss.vitalsstream",
            }
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kafka")
        self.assertEqual(ctx.topic, "wss.vitalsstream")


class TestAlertForPrompt(unittest.TestCase):
    def test_strips_fake_k8s_labels_for_kafka(self):
        alert = _alert(
            {
                "alertname": "pod.restart.vitalsstream",
                "severity": "critical",
                "namespace": "msk",
                "pod": "should-not-appear",
                "container": "also-gone",
                "job": "msk-kb",
                "topic": "wss.vitalsstream",
            }
        )
        ctx = build_alert_context(alert)
        sanitized = alert_for_prompt(alert, ctx)
        labels = sanitized["labels"]

        self.assertNotIn("namespace", labels)
        self.assertNotIn("pod", labels)
        self.assertNotIn("container", labels)
        self.assertEqual(labels["topic"], "wss.vitalsstream")

    def test_keeps_k8s_labels_for_kubernetes(self):
        alert = _alert(
            {
                "alertname": "PodRestarting",
                "namespace": "production",
                "pod": "api-server-7f8c9d",
            }
        )
        ctx = build_alert_context(alert)
        sanitized = alert_for_prompt(alert, ctx)
        labels = sanitized["labels"]

        self.assertEqual(labels["namespace"], "production")
        self.assertEqual(labels["pod"], "api-server-7f8c9d")

    def test_sample_webhook_file(self):
        sample_path = SAMPLE_DIR / "pod-restart-vitalsstream-alert.json"
        payload = json.loads(sample_path.read_text())
        alert = payload["alerts"][0]
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "kafka")
        self.assertIn("related_workload", ctx.to_prompt_block())

    def test_ec2_host_context_fields(self):
        alert = _alert(
            {
                "alertname": "EC2HostMemoryUnderMemoryPressure",
                "severity": "warning",
                "namespace": "ec2",
                "instance": "10.1.64.41:9100",
            },
            {
                "description": "Heavy memory pressure\n  VALUE = 1423.2",
            },
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.resource_type, "host")
        self.assertEqual(ctx.scrape_job, "AWSEC2NodeExporter")
        self.assertEqual(ctx.alert_firing_value, 1423.2)
        self.assertEqual(ctx.primary_metric, "major_page_faults_per_sec")
        self.assertIn("scrape_job: AWSEC2NodeExporter", ctx.to_prompt_block())

    def test_external_labels_on_context(self):
        alert = _alert(
            {
                "alertname": "PODCPULimitsUage>=90",
                "severity": "critical",
                "namespace": "dozeeplatform",
                "pod": "consumer-abc",
                "container": "consumer",
                "region": "ap-south-1",
                "cloud": "aws",
                "stage": "prod",
            }
        )
        ctx = build_alert_context(alert)

        self.assertEqual(ctx.region, "ap-south-1")
        self.assertEqual(ctx.cloud, "aws")
        self.assertEqual(ctx.stage, "prod")
        self.assertIn("region: ap-south-1", ctx.to_prompt_block())


if __name__ == "__main__":
    unittest.main()
