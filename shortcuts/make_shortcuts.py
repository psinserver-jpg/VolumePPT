#!/usr/bin/env python3
"""아이폰 단축어 파일(VolumePPT 다음 / VolumePPT 이전) 생성기.

두 단축어는 사용자마다 다른 PC 주소/PIN 을 담지 않는 '공용' 단축어다.
주소는 처음 한 번 웹 리모컨의 [이 PC 로 설정] 버튼이 넘겨주는 값을
iCloud Drive/Shortcuts/VolumePPT.txt 에 저장해 두고 매번 읽어 쓴다.

    입력이 있으면 (설정)   → VolumePPT.txt 에 저장하고 "설정 완료" 알림
    입력이 없으면 (실행)   → VolumePPT.txt 를 읽어 ACTION 을 next/prev 로 바꾼 URL 호출

저장되는 값의 예:  http://100.101.102.103:8765/ACTION?token=4321

만들어진 .shortcut 은 서명 전 파일이다. iOS 15 이상에서 가져오려면 Mac 에서
    shortcuts sign --mode anyone --input X.shortcut --output X-signed.shortcut
으로 서명해야 한다 (GitHub Actions 의 macOS 빌드에서 자동으로 수행).
"""

import os
import plistlib
import sys
import uuid

CONFIG_FILE = "VolumePPT.txt"
SHORTCUTS = {
    "next": "VolumePPT 다음",
    "prev": "VolumePPT 이전",
}


def _uuid():
    return str(uuid.uuid4()).upper()


def _input_var():
    return {"Value": {"Type": "ExtensionInput"}, "WFSerializationType": "WFTextTokenAttachment"}


def _output_var(output_uuid, name):
    return {"Value": {"Type": "ActionOutput", "OutputUUID": output_uuid, "OutputName": name},
            "WFSerializationType": "WFTextTokenAttachment"}


def _text_with_output(output_uuid, name):
    """텍스트 칸 전체가 이전 동작의 결과 하나인 경우."""
    return {"Value": {"string": "￼",
                      "attachmentsByRange": {"{0, 1}": {"Type": "ActionOutput", "OutputUUID": output_uuid,
                                                        "OutputName": name}}},
            "WFSerializationType": "WFTextTokenString"}


def _action(identifier, **params):
    return {"WFWorkflowActionIdentifier": identifier, "WFWorkflowActionParameters": params}


def build(action):
    group = _uuid()
    file_uuid = _uuid()
    text_uuid = _uuid()
    url_uuid = _uuid()
    label = "다음" if action == "next" else "이전"

    actions = [
        # 만약 [단축어 입력] 에 값이 있으면 → 설정 저장
        _action("is.workflow.actions.conditional",
                GroupingIdentifier=group, WFControlFlowMode=0,
                WFCondition=100,                      # "값이 있음"
                WFInput={"Type": "Variable", "Variable": _input_var()}),
        _action("is.workflow.actions.documentpicker.save",
                WFInput=_input_var(),
                WFAskWhereToSave=False,
                WFFileDestinationPath=CONFIG_FILE,
                WFSaveFileOverwrite=True),
        _action("is.workflow.actions.notification",
                WFNotificationActionTitle="VolumePPT",
                WFNotificationActionBody="설정 완료! 이제 이 단축어로 슬라이드를 넘길 수 있습니다.",
                WFNotificationActionSound=False),
        # 아니면 → 저장된 주소로 요청
        _action("is.workflow.actions.conditional",
                GroupingIdentifier=group, WFControlFlowMode=1),
        _action("is.workflow.actions.documentpicker.open",
                UUID=file_uuid,
                WFGetFilePath=CONFIG_FILE,
                WFFileErrorIfNotFound=True,
                WFShowFilePicker=False),
        _action("is.workflow.actions.text.replace",
                UUID=text_uuid,
                WFInput=_text_with_output(file_uuid, "File"),
                WFReplaceTextFind="ACTION",
                WFReplaceTextReplace=action),
        _action("is.workflow.actions.downloadurl",
                UUID=url_uuid,
                WFURL=_text_with_output(text_uuid, "Updated Text"),
                WFHTTPMethod="GET"),
        _action("is.workflow.actions.conditional",
                GroupingIdentifier=group, WFControlFlowMode=2),
    ]

    return {
        "WFWorkflowClientVersion": "2302.0.4",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 463140863,   # 파랑
                           "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": [],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFURLContentItem"],
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowOutputContentItemClasses": [],
        "WFQuickActionSurfaces": [],
        "WFWorkflowActions": actions,
        "WFWorkflowName": SHORTCUTS[action],
        "WFWorkflowComment": f"VolumePPT: PowerPoint {label} 슬라이드",
    }


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for action in SHORTCUTS:
        path = os.path.join(out_dir, f"VolumePPT-{action}.shortcut")
        with open(path, "wb") as f:
            plistlib.dump(build(action), f, fmt=plistlib.FMT_BINARY)
        print(path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
