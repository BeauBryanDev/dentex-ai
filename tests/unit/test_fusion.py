"""Dedup and lesion attribution, the two ordered stages of fusion."""
from __future__ import annotations

import pytest

from app.services.fusion import assign_lesions, dedup_teeth, fuse
from tests.unit.conftest import TOOTH_ID_BY_FDI, make_detections

CROWN_ID = 1
T43, T44 = TOOTH_ID_BY_FDI[43], TOOTH_ID_BY_FDI[44]
T37 = TOOTH_ID_BY_FDI[37]


def test_dedup_never_suppresses_a_restoration_over_its_tooth():
    teeth = make_detections(
        boxes=[[100, 100, 140, 180], [100, 100, 140, 180]],
        scores=[0.9, 0.85],
        class_ids=[T44, CROWN_ID],
        labels=["T44", "Crown"],
    )
    kept = dedup_teeth(teeth, 0.7)
    assert sorted(kept.labels) == ["Crown", "T44"]


def test_dedup_ranks_by_raw_score_when_boosted_scores_both_clamp():
    ## the boost saturates most FDI scores at 1.0, so ranking must use the model's own number
    teeth = make_detections(
        boxes=[[100, 100, 140, 180], [101, 101, 141, 181]],
        scores=[1.0, 1.0],
        class_ids=[T43, T44],
        labels=["T43", "T44"],
        raw_scores=[0.81, 0.97],
    )
    assert dedup_teeth(teeth, 0.7).labels == ["T44"]


def test_assign_lesions_attributes_a_lesion_iou_would_have_dropped():
    lesions = make_detections([[110, 120, 130, 140]], [0.6], [0], labels=["Cavities"])
    teeth = make_detections([[100, 100, 200, 220]], [0.9], [T37], labels=["T37"])
    findings = assign_lesions(lesions, teeth, 0.15)
    assert findings[0].tooth_fdi == 37
    assert findings[0].tooth_anatomy == "lower_left_second_molar"
    assert findings[0].containment == pytest.approx(1.0)


def test_assign_lesions_returns_unattributed_lesions_rather_than_dropping_them():
    lesions = make_detections([[500, 500, 520, 520]], [0.6], [1], labels=["Damage"])
    teeth = make_detections([[100, 100, 200, 220]], [0.9], [T37], labels=["T37"])
    findings = assign_lesions(lesions, teeth, 0.15)
    assert len(findings) == 1
    assert findings[0].tooth_fdi is None
    assert "unattributed" in findings[0].describe()


def test_fuse_never_attributes_a_lesion_to_a_discarded_fdi_number():
    teeth = make_detections(
        boxes=[[100, 100, 200, 220], [101, 101, 201, 221]],
        scores=[0.9, 0.4],
        class_ids=[T37, T43],
        labels=["T37", "T43"],
        raw_scores=[0.9, 0.4],
    )
    lesions = make_detections([[110, 120, 130, 140]], [0.6], [0], labels=["Cavities"])
    findings, kept = fuse(lesions, teeth, 0.7, 0.15)
    assert [t for t in kept.labels] == ["T37"]
    assert findings[0].tooth_fdi == 37


