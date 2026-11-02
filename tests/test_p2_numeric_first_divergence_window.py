"""P2 numeric first-divergence window: stdlib-only safety contracts (no Docker/GPU)."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from src import p2_numeric_first_divergence_window as w


class NumericWindowTests(unittest.TestCase):
    def test_image_tag_labels_are_pinned(self):
        self.assertTrue(w.tag("a" * 40).endswith(":" + "a" * 12))
        self.assertEqual(w.labels("a" * 40)[w.LABEL + ".base-id"], w.ORIGINAL_IMAGE)
        with self.assertRaisesRegex(w.Blocked, "HEAD_SHA_REQUIRED"):
            w.tag("latest")

    def test_verify_image_strict_ancestry_and_default_off(self):
        base = {"Id": w.ORIGINAL_IMAGE, "RootFS": {"Layers": ["l1", "l2"]},
                "Config": {"Cmd": ["serve"], "Entrypoint": None,
                           "User": "", "WorkingDir": ""}}
        child = {"Id": "sha256:" + "2"*64,
                 "RootFS": {"Layers": ["l1", "l2", "l3"]},
                 "Config": {**base["Config"],
                            "Labels": w.labels("a"*40),
                            "Env": ["VLLM_P2_NUMERIC_WITNESS=0",
                                    "VLLM_PLE_UNIQUE_H2D=0",
                                    "VLLM_P2_DRAFT_VOCAB=",
                                    "VLLM_P2_DRAFT_VOCAB_SHA256="]}}
        def inspect(_, name):
            return base if name == w.legacy.IMAGE_TAG else child
        with patch.object(w.legacy, "inspect", side_effect=inspect):
            self.assertIs(w.verify_image("a"*40), child)
        child["RootFS"]["Layers"] = ["l1", "l2"]
        with patch.object(w.legacy, "inspect", side_effect=inspect):
            with self.assertRaisesRegex(w.Blocked, "ANCESTRY_DRIFT"):
                w.verify_image("a"*40)

    def test_minimal_source_stage_exact_integrity(self):
        with tempfile.TemporaryDirectory(dir="/tmp", prefix=w.minimal.SINGLE_CANDIDATE_PREFIX) as temp:
            folder=Path(temp);folder.chmod(0o700)
            raw=b"mock-sampler-witness"
            d=w.minimal.numeric_only_dockerfile()
            receipt={"status":"P2_MINIMAL_NUMERIC_SOURCE_PLAN_NO_GPU_AUTHORIZATION",
                     "sampler_sha256":hashlib.sha256(raw).hexdigest(),
                     "dockerfile_sha256":hashlib.sha256(d).hexdigest(),
                     "original_id_verified":True, "original_image_verified":True,
                     "numeric_witness_default_off":True,
                     "gpu_window_authorized":False,"image_build_authorized":False}
            for name,data in (("sampler.py",raw),("Dockerfile",d),
                              ("receipt.json",json.dumps(receipt).encode())):
                p=folder/name;p.write_bytes(data);p.chmod(0o600)
            with patch.dict(w.minimal.PIN_SOURCE_HASHES, {"sampler.py":receipt["sampler_sha256"]}, clear=False):
                self.assertTrue(w.verify_minimal_stage(folder)["minimal_stage_pinned"])
                (folder/"sampler.py").write_bytes(raw+b"-tamper")
                with self.assertRaisesRegex(w.Blocked, "SHA_DRIFT"):
                    w.verify_minimal_stage(folder)
                (folder/"sampler.py").write_bytes(raw)
                (folder/"receipt.json").chmod(0o644)
                with self.assertRaisesRegex(w.Blocked, "MODE_OR_SIZE"):
                    w.verify_minimal_stage(folder)

    def test_preflight_does_not_modify_or_build(self):
        with patch.object(w.trace, "original_identity", return_value=("id","image","start")), \
             patch.object(w, "verify_minimal_stage") as stage, \
             patch.object(w.minimal, "read_only_original_guard") as guard, \
             patch.object(w, "absent_candidates") as absent, \
             patch.object(w, "original_running", return_value=({}, {"Config":{"Cmd":["stock"]}}, {}, "running")), \
             patch.object(w.mtp_off, "args_for", return_value=([], "model")), \
             patch.object(w.release, "_run") as run:
            info=w.image_preflight("a"*40, Path("/tmp/mock"))
        stage.assert_called_once();guard.assert_called_once();absent.assert_called_once()
        run.assert_not_called()
        self.assertFalse(info["gpu_not_executed"] is False)
        self.assertFalse(info["service_outage_performed"])

    def test_preflight_started_at_drift_blocks(self):
        with patch.object(w.trace, "original_identity",
                          side_effect=[("id","image","before"), ("id","image","after")]), \
             patch.object(w, "verify_minimal_stage"), \
             patch.object(w.minimal, "read_only_original_guard"), \
             patch.object(w, "absent_candidates"), \
             patch.object(w, "original_running",
                          return_value=({}, {"Config":{"Cmd":["stock"]}}, {}, "running")), \
             patch.object(w.mtp_off, "args_for", return_value=([], "model")):
            with self.assertRaisesRegex(w.Blocked, "START_TIME_CHANGED"):
                w.image_preflight("a"*40, Path("/tmp/mock"))

    def test_candidate_runtime_adds_only_sampler_flag_and_raw_logprobs(self):
        head="a"*40
        original_cmd=["vllm", "serve", "--no-enable-prefix-caching",
                      "--host", "0.0.0.0", "--port", "8000"]
        template=["docker","create","--gpus=all","--network=bridge",
                  "--name", w.mtp_off.NAME,
                  "--label", w.mtp_off.LABEL+"="+head,
                  "--label", w.mtp_off.LABEL+".image-id="+w.ORIGINAL_IMAGE,
                  w.mtp_off.TAG, *original_cmd]
        with patch.object(w.mtp_off, "args_for",
                          return_value=(template, "model")):
            args,_=w.args_for(head, {}, {}, {}, "sha256:"+"2"*64)
        self.assertEqual(args.count("VLLM_P2_NUMERIC_WITNESS=1"),1)
        self.assertEqual(args.count("--logprobs-mode"),1)
        self.assertIn("raw_logprobs",args)
        self.assertNotIn("--speculative-config",args)
        self.assertIn("--no-enable-prefix-caching",args)
        self.assertEqual(args.count("--gpus=all"),1)

    def test_candidate_existing_unexpected_logprob_mode_blocks(self):
        head="a"*40
        template=["docker","create",w.mtp_off.TAG,"--logprobs-mode","processed_logprobs"]
        with patch.object(w.mtp_off, "args_for", return_value=(template, "model")):
            with self.assertRaisesRegex(w.Blocked, "LOGPROBS_MODE_CONFLICT"):
                w.args_for(head, {}, {}, {}, "sha256:"+"2"*64)

    def test_no_two_models_restore_rule_on_candidate(self):
        with patch.object(w.mtp_off,"inspect_original",return_value=({"id":w.ORIGINAL_ID},{},{}, "running")), \
             patch.object(w,"candidate_ids",return_value=["a"*64]), \
             patch.object(w,"cleanup") as cleanup, \
             patch.object(w.b,"restore_original") as restart:
            with self.assertRaisesRegex(w.Blocked,"TWO_MODELS"):
                w.restore("a"*40,"sha256:"+"2"*64,"model")
        cleanup.assert_not_called();restart.assert_not_called()

    def test_restoration_removes_owned_before_restarting_exact_original(self):
        events=[]
        with patch.object(w.mtp_off,"inspect_original",return_value=({"id":w.ORIGINAL_ID},{},{}, "exited")), \
             patch.object(w,"candidate_ids",side_effect=[["a"*64],[],[]]), \
             patch.object(w,"cleanup",side_effect=lambda *x:events.append("clean")) as cleanup, \
             patch.object(w.b,"restore_original",side_effect=lambda *x:events.append("restart")) as restart, \
             patch.object(w.window,"check_original_running",side_effect=lambda *x:events.append("http")), \
             patch.object(w.window,"notify"):
            w.restore("a"*40,"sha256:"+"2"*64,"model")
        self.assertEqual(events,["clean","restart","http"])
        cleanup.assert_called_once();restart.assert_called_once()

    def test_execute_failure_after_stop_runs_restore_in_finally(self):
        head="a"*40;img="sha256:"+"2"*64
        with patch.object(w,"image_preflight"), \
             patch.object(w,"verify_image",return_value={"Id":img}), \
             patch.object(w,"original_running",return_value=({"id":w.ORIGINAL_ID},{},{}, "running")), \
             patch.object(w,"args_for",return_value=(["docker","create"],"model")), \
             patch.object(w,"absent_candidates"), \
             patch.object(w.window,"check_original_running"), \
             patch.object(w.window,"stop_original",side_effect=RuntimeError("stop failure")), \
             patch.object(w,"restore") as recovered, \
             patch.object(w.window,"notify"):
            with self.assertRaisesRegex(RuntimeError,"stop failure"):
                w.execute(head,Path("/tmp/not-read"),w.ORIGINAL_ID,w.ORIGINAL_IMAGE)
        recovered.assert_called_once_with(head,img,"model")

    def test_first_token_measurement_report_has_no_raw_ids(self):
        runs=[{"token_ids":[7],"logprobs":[-1.0],"finish_reason":"length"} for _ in range(4)]
        with patch.object(w,"first_token",side_effect=runs) as call, \
             patch.object(w,"read_witness",return_value=[{"mock":1}]*4), \
             patch.object(w.report,"analyze_payload",
                          return_value={"provenance_verified":False,"reason":"MISSING"}):
            result=w.measure("a"*40,"sha256:"+"2"*64,"a"*64,"model")
        self.assertEqual(call.call_count,4)
        self.assertEqual(result["requests"],4)
        self.assertNotIn("token_ids",json.dumps(result))
        self.assertFalse(result["release_approved"])

    def test_witness_parser_rejects_oversize_and_bad_event_count(self):
        entry=b"P2_NUMERIC_WITNESS "+json.dumps({"sequence":1}).encode()+b"\n"
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode="w") as tf:
            ti=tarfile.TarInfo("p2-numeric-witness.jsonl");ti.size=len(entry)
            tf.addfile(ti,io.BytesIO(entry))
        payload=buf.getvalue()
        with patch.object(w.subprocess,"run",return_value=Mock(returncode=0,stdout=payload)):
            with self.assertRaisesRegex(w.Blocked,"EVENT_COUNT"):
                w.read_witness("a"*64)

    def test_authorization_pins_fail_before_service_stop(self):
        with patch.object(w,"image_preflight") as preflight, \
             patch.object(w.window,"stop_original") as stop:
            with self.assertRaisesRegex(w.Blocked,"CONFIRMATION_REQUIRED"):
                w.execute("a"*40,Path("/tmp/fake"),"bad","bad")
        preflight.assert_not_called();stop.assert_not_called()


if __name__=="__main__":
    unittest.main()
