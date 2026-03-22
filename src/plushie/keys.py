"""Key name constants matching the plushie wire protocol values.

Provides typo safety and IDE completion for key names used in keyboard
event matching. Each value is the exact string sent over the wire by the
Rust binary (iced's Debug format for ``keyboard::key::Named`` variants
and physical ``KeyCode`` variants).

Usage::

    from plushie.events import KeyPress
    from plushie import keys

    match event:
        case KeyPress(key=k) if k == keys.ESCAPE:
            handle_escape(model)
        case KeyPress(key=k) if k == keys.ENTER:
            handle_enter(model)
        case _:
            model
"""

from __future__ import annotations

# --- Navigation ---

ESCAPE: str = "Escape"
ENTER: str = "Enter"
TAB: str = "Tab"
BACKSPACE: str = "Backspace"
DELETE: str = "Delete"
ARROW_UP: str = "ArrowUp"
ARROW_DOWN: str = "ArrowDown"
ARROW_LEFT: str = "ArrowLeft"
ARROW_RIGHT: str = "ArrowRight"
HOME: str = "Home"
END: str = "End"
PAGE_UP: str = "PageUp"
PAGE_DOWN: str = "PageDown"
SPACE: str = "Space"
INSERT: str = "Insert"
CLEAR: str = "Clear"

# --- Modifier keys ---

ALT: str = "Alt"
ALT_GRAPH: str = "AltGraph"
CAPS_LOCK: str = "CapsLock"
CONTROL: str = "Control"
FN: str = "Fn"
FN_LOCK: str = "FnLock"
NUM_LOCK: str = "NumLock"
SCROLL_LOCK: str = "ScrollLock"
SHIFT: str = "Shift"
SYMBOL: str = "Symbol"
SYMBOL_LOCK: str = "SymbolLock"
META: str = "Meta"
HYPER: str = "Hyper"
SUPER: str = "Super"

# --- Editing keys ---

COPY: str = "Copy"
CUT: str = "Cut"
PASTE: str = "Paste"
REDO: str = "Redo"
UNDO: str = "Undo"
CR_SEL: str = "CrSel"
ERASE_EOF: str = "EraseEof"
EX_SEL: str = "ExSel"

# --- UI keys ---

ACCEPT: str = "Accept"
AGAIN: str = "Again"
ATTN: str = "Attn"
CANCEL: str = "Cancel"
CONTEXT_MENU: str = "ContextMenu"
EXECUTE: str = "Execute"
FIND: str = "Find"
HELP: str = "Help"
PAUSE: str = "Pause"
PLAY: str = "Play"
PROPS: str = "Props"
SELECT: str = "Select"
ZOOM_IN: str = "ZoomIn"
ZOOM_OUT: str = "ZoomOut"

# --- System keys ---

BRIGHTNESS_DOWN: str = "BrightnessDown"
BRIGHTNESS_UP: str = "BrightnessUp"
EJECT: str = "Eject"
LOG_OFF: str = "LogOff"
POWER: str = "Power"
POWER_OFF: str = "PowerOff"
PRINT_SCREEN: str = "PrintScreen"
HIBERNATE: str = "Hibernate"
STANDBY: str = "Standby"
WAKE_UP: str = "WakeUp"

# --- Function keys ---

F1: str = "F1"
F2: str = "F2"
F3: str = "F3"
F4: str = "F4"
F5: str = "F5"
F6: str = "F6"
F7: str = "F7"
F8: str = "F8"
F9: str = "F9"
F10: str = "F10"
F11: str = "F11"
F12: str = "F12"
F13: str = "F13"
F14: str = "F14"
F15: str = "F15"
F16: str = "F16"
F17: str = "F17"
F18: str = "F18"
F19: str = "F19"
F20: str = "F20"
F21: str = "F21"
F22: str = "F22"
F23: str = "F23"
F24: str = "F24"
F25: str = "F25"
F26: str = "F26"
F27: str = "F27"
F28: str = "F28"
F29: str = "F29"
F30: str = "F30"
F31: str = "F31"
F32: str = "F32"
F33: str = "F33"
F34: str = "F34"
F35: str = "F35"

# --- Media keys ---

CHANNEL_DOWN: str = "ChannelDown"
CHANNEL_UP: str = "ChannelUp"
CLOSE: str = "Close"
MAIL_FORWARD: str = "MailForward"
MAIL_REPLY: str = "MailReply"
MAIL_SEND: str = "MailSend"
MEDIA_CLOSE: str = "MediaClose"
MEDIA_FAST_FORWARD: str = "MediaFastForward"
MEDIA_PAUSE: str = "MediaPause"
MEDIA_PLAY: str = "MediaPlay"
MEDIA_PLAY_PAUSE: str = "MediaPlayPause"
MEDIA_RECORD: str = "MediaRecord"
MEDIA_REWIND: str = "MediaRewind"
MEDIA_STOP: str = "MediaStop"
MEDIA_TRACK_NEXT: str = "MediaTrackNext"
MEDIA_TRACK_PREVIOUS: str = "MediaTrackPrevious"
NEW: str = "New"
OPEN: str = "Open"
PRINT: str = "Print"
SAVE: str = "Save"
SPELL_CHECK: str = "SpellCheck"

# --- Audio keys ---

AUDIO_BALANCE_LEFT: str = "AudioBalanceLeft"
AUDIO_BALANCE_RIGHT: str = "AudioBalanceRight"
AUDIO_BASS_BOOST_DOWN: str = "AudioBassBoostDown"
AUDIO_BASS_BOOST_TOGGLE: str = "AudioBassBoostToggle"
AUDIO_BASS_BOOST_UP: str = "AudioBassBoostUp"
AUDIO_FADER_FRONT: str = "AudioFaderFront"
AUDIO_FADER_REAR: str = "AudioFaderRear"
AUDIO_SURROUND_MODE_NEXT: str = "AudioSurroundModeNext"
AUDIO_TREBLE_DOWN: str = "AudioTrebleDown"
AUDIO_TREBLE_UP: str = "AudioTrebleUp"
AUDIO_VOLUME_DOWN: str = "AudioVolumeDown"
AUDIO_VOLUME_UP: str = "AudioVolumeUp"
AUDIO_VOLUME_MUTE: str = "AudioVolumeMute"

# --- Microphone keys ---

MICROPHONE_TOGGLE: str = "MicrophoneToggle"
MICROPHONE_VOLUME_DOWN: str = "MicrophoneVolumeDown"
MICROPHONE_VOLUME_UP: str = "MicrophoneVolumeUp"
MICROPHONE_VOLUME_MUTE: str = "MicrophoneVolumeMute"

# --- Speech keys ---

SPEECH_CORRECTION_LIST: str = "SpeechCorrectionList"
SPEECH_INPUT_TOGGLE: str = "SpeechInputToggle"

# --- Launch keys ---

LAUNCH_APPLICATION1: str = "LaunchApplication1"
LAUNCH_APPLICATION2: str = "LaunchApplication2"
LAUNCH_CALENDAR: str = "LaunchCalendar"
LAUNCH_CONTACTS: str = "LaunchContacts"
LAUNCH_MAIL: str = "LaunchMail"
LAUNCH_MEDIA_PLAYER: str = "LaunchMediaPlayer"
LAUNCH_MUSIC_PLAYER: str = "LaunchMusicPlayer"
LAUNCH_PHONE: str = "LaunchPhone"
LAUNCH_SCREEN_SAVER: str = "LaunchScreenSaver"
LAUNCH_SPREADSHEET: str = "LaunchSpreadsheet"
LAUNCH_WEB_BROWSER: str = "LaunchWebBrowser"
LAUNCH_WEB_CAM: str = "LaunchWebCam"
LAUNCH_WORD_PROCESSOR: str = "LaunchWordProcessor"

# --- Browser keys ---

BROWSER_BACK: str = "BrowserBack"
BROWSER_FAVORITES: str = "BrowserFavorites"
BROWSER_FORWARD: str = "BrowserForward"
BROWSER_HOME: str = "BrowserHome"
BROWSER_REFRESH: str = "BrowserRefresh"
BROWSER_SEARCH: str = "BrowserSearch"
BROWSER_STOP: str = "BrowserStop"

# --- IME keys ---

ALL_CANDIDATES: str = "AllCandidates"
ALPHANUMERIC: str = "Alphanumeric"
CODE_INPUT: str = "CodeInput"
COMPOSE: str = "Compose"
CONVERT: str = "Convert"
FINAL_MODE: str = "FinalMode"
GROUP_FIRST: str = "GroupFirst"
GROUP_LAST: str = "GroupLast"
GROUP_NEXT: str = "GroupNext"
GROUP_PREVIOUS: str = "GroupPrevious"
MODE_CHANGE: str = "ModeChange"
NEXT_CANDIDATE: str = "NextCandidate"
NON_CONVERT: str = "NonConvert"
PREVIOUS_CANDIDATE: str = "PreviousCandidate"
PROCESS: str = "Process"
SINGLE_CANDIDATE: str = "SingleCandidate"

# --- Korean IME ---

HANGUL_MODE: str = "HangulMode"
HANJA_MODE: str = "HanjaMode"
JUNJA_MODE: str = "JunjaMode"

# --- Japanese IME ---

EISU: str = "Eisu"
HANKAKU: str = "Hankaku"
HIRAGANA: str = "Hiragana"
HIRAGANA_KATAKANA: str = "HiraganaKatakana"
KANA_MODE: str = "KanaMode"
KANJI_MODE: str = "KanjiMode"
KATAKANA: str = "Katakana"
ROMAJI: str = "Romaji"
ZENKAKU: str = "Zenkaku"
ZENKAKU_HANKAKU: str = "ZenkakuHankaku"

# --- Soft keys ---

SOFT1: str = "Soft1"
SOFT2: str = "Soft2"
SOFT3: str = "Soft3"
SOFT4: str = "Soft4"

# --- Mobile / phone keys ---

APP_SWITCH: str = "AppSwitch"
CALL: str = "Call"
CAMERA: str = "Camera"
CAMERA_FOCUS: str = "CameraFocus"
END_CALL: str = "EndCall"
GO_BACK: str = "GoBack"
GO_HOME: str = "GoHome"
HEADSET_HOOK: str = "HeadsetHook"
LAST_NUMBER_REDIAL: str = "LastNumberRedial"
NOTIFICATION: str = "Notification"
MANNER_MODE: str = "MannerMode"
VOICE_DIAL: str = "VoiceDial"

# --- Numpad keys ---

KEY11: str = "Key11"
KEY12: str = "Key12"
NUMPAD_BACKSPACE: str = "NumpadBackspace"
NUMPAD_CLEAR: str = "NumpadClear"
NUMPAD_CLEAR_ENTRY: str = "NumpadClearEntry"
NUMPAD_COMMA: str = "NumpadComma"
NUMPAD_DECIMAL: str = "NumpadDecimal"
NUMPAD_DIVIDE: str = "NumpadDivide"
NUMPAD_ENTER: str = "NumpadEnter"
NUMPAD_EQUAL: str = "NumpadEqual"
NUMPAD_HASH: str = "NumpadHash"
NUMPAD_MEMORY_ADD: str = "NumpadMemoryAdd"
NUMPAD_MEMORY_CLEAR: str = "NumpadMemoryClear"
NUMPAD_MEMORY_RECALL: str = "NumpadMemoryRecall"
NUMPAD_MEMORY_STORE: str = "NumpadMemoryStore"
NUMPAD_MEMORY_SUBTRACT: str = "NumpadMemorySubtract"
NUMPAD_MULTIPLY: str = "NumpadMultiply"
NUMPAD_PAREN_LEFT: str = "NumpadParenLeft"
NUMPAD_PAREN_RIGHT: str = "NumpadParenRight"
NUMPAD_STAR: str = "NumpadStar"
NUMPAD_SUBTRACT: str = "NumpadSubtract"

# --- TV keys ---

TV: str = "TV"
TV_3D_MODE: str = "TV3DMode"
TV_ANTENNA_CABLE: str = "TVAntennaCable"
TV_AUDIO_DESCRIPTION: str = "TVAudioDescription"
TV_AUDIO_DESCRIPTION_MIX_DOWN: str = "TVAudioDescriptionMixDown"
TV_AUDIO_DESCRIPTION_MIX_UP: str = "TVAudioDescriptionMixUp"
TV_CONTENTS_MENU: str = "TVContentsMenu"
TV_DATA_SERVICE: str = "TVDataService"
TV_INPUT: str = "TVInput"
TV_INPUT_COMPONENT1: str = "TVInputComponent1"
TV_INPUT_COMPONENT2: str = "TVInputComponent2"
TV_INPUT_COMPOSITE1: str = "TVInputComposite1"
TV_INPUT_COMPOSITE2: str = "TVInputComposite2"
TV_INPUT_HDMI1: str = "TVInputHDMI1"
TV_INPUT_HDMI2: str = "TVInputHDMI2"
TV_INPUT_HDMI3: str = "TVInputHDMI3"
TV_INPUT_HDMI4: str = "TVInputHDMI4"
TV_INPUT_VGA1: str = "TVInputVGA1"
TV_MEDIA_CONTEXT: str = "TVMediaContext"
TV_NETWORK: str = "TVNetwork"
TV_NUMBER_ENTRY: str = "TVNumberEntry"
TV_POWER: str = "TVPower"
TV_RADIO_SERVICE: str = "TVRadioService"
TV_SATELLITE: str = "TVSatellite"
TV_SATELLITE_BS: str = "TVSatelliteBS"
TV_SATELLITE_CS: str = "TVSatelliteCS"
TV_SATELLITE_TOGGLE: str = "TVSatelliteToggle"
TV_TERRESTRIAL_ANALOG: str = "TVTerrestrialAnalog"
TV_TERRESTRIAL_DIGITAL: str = "TVTerrestrialDigital"
TV_TIMER: str = "TVTimer"

# --- Special ---

UNIDENTIFIED: str = "Unidentified"

# --- Physical key codes ---
# These match the Rust KeyCode Debug format (e.g. "KeyA", "Digit0").

KEY_A: str = "KeyA"
KEY_B: str = "KeyB"
KEY_C: str = "KeyC"
KEY_D: str = "KeyD"
KEY_E: str = "KeyE"
KEY_F: str = "KeyF"
KEY_G: str = "KeyG"
KEY_H: str = "KeyH"
KEY_I: str = "KeyI"
KEY_J: str = "KeyJ"
KEY_K: str = "KeyK"
KEY_L: str = "KeyL"
KEY_M: str = "KeyM"
KEY_N: str = "KeyN"
KEY_O: str = "KeyO"
KEY_P: str = "KeyP"
KEY_Q: str = "KeyQ"
KEY_R: str = "KeyR"
KEY_S: str = "KeyS"
KEY_T: str = "KeyT"
KEY_U: str = "KeyU"
KEY_V: str = "KeyV"
KEY_W: str = "KeyW"
KEY_X: str = "KeyX"
KEY_Y: str = "KeyY"
KEY_Z: str = "KeyZ"

DIGIT_0: str = "Digit0"
DIGIT_1: str = "Digit1"
DIGIT_2: str = "Digit2"
DIGIT_3: str = "Digit3"
DIGIT_4: str = "Digit4"
DIGIT_5: str = "Digit5"
DIGIT_6: str = "Digit6"
DIGIT_7: str = "Digit7"
DIGIT_8: str = "Digit8"
DIGIT_9: str = "Digit9"

SHIFT_LEFT: str = "ShiftLeft"
SHIFT_RIGHT: str = "ShiftRight"
CONTROL_LEFT: str = "ControlLeft"
CONTROL_RIGHT: str = "ControlRight"
ALT_LEFT: str = "AltLeft"
ALT_RIGHT: str = "AltRight"
META_LEFT: str = "MetaLeft"
META_RIGHT: str = "MetaRight"

MINUS: str = "Minus"
EQUAL: str = "Equal"
BRACKET_LEFT: str = "BracketLeft"
BRACKET_RIGHT: str = "BracketRight"
BACKSLASH: str = "Backslash"
SEMICOLON: str = "Semicolon"
QUOTE: str = "Quote"
BACKQUOTE: str = "Backquote"
COMMA: str = "Comma"
PERIOD: str = "Period"
SLASH: str = "Slash"

NUMPAD_0: str = "Numpad0"
NUMPAD_1: str = "Numpad1"
NUMPAD_2: str = "Numpad2"
NUMPAD_3: str = "Numpad3"
NUMPAD_4: str = "Numpad4"
NUMPAD_5: str = "Numpad5"
NUMPAD_6: str = "Numpad6"
NUMPAD_7: str = "Numpad7"
NUMPAD_8: str = "Numpad8"
NUMPAD_9: str = "Numpad9"
NUMPAD_ADD: str = "NumpadAdd"

__all__ = [
    "ACCEPT",
    "AGAIN",
    "ALL_CANDIDATES",
    "ALPHANUMERIC",
    "ALT",
    "ALT_GRAPH",
    "ALT_LEFT",
    "ALT_RIGHT",
    "APP_SWITCH",
    "ARROW_DOWN",
    "ARROW_LEFT",
    "ARROW_RIGHT",
    "ARROW_UP",
    "ATTN",
    "AUDIO_BALANCE_LEFT",
    "AUDIO_BALANCE_RIGHT",
    "AUDIO_BASS_BOOST_DOWN",
    "AUDIO_BASS_BOOST_TOGGLE",
    "AUDIO_BASS_BOOST_UP",
    "AUDIO_FADER_FRONT",
    "AUDIO_FADER_REAR",
    "AUDIO_SURROUND_MODE_NEXT",
    "AUDIO_TREBLE_DOWN",
    "AUDIO_TREBLE_UP",
    "AUDIO_VOLUME_DOWN",
    "AUDIO_VOLUME_MUTE",
    "AUDIO_VOLUME_UP",
    "BACKQUOTE",
    "BACKSLASH",
    "BACKSPACE",
    "BRACKET_LEFT",
    "BRACKET_RIGHT",
    "BRIGHTNESS_DOWN",
    "BRIGHTNESS_UP",
    "BROWSER_BACK",
    "BROWSER_FAVORITES",
    "BROWSER_FORWARD",
    "BROWSER_HOME",
    "BROWSER_REFRESH",
    "BROWSER_SEARCH",
    "BROWSER_STOP",
    "CALL",
    "CAMERA",
    "CAMERA_FOCUS",
    "CANCEL",
    "CAPS_LOCK",
    "CHANNEL_DOWN",
    "CHANNEL_UP",
    "CLEAR",
    "CLOSE",
    "CODE_INPUT",
    "COMMA",
    "COMPOSE",
    "CONTEXT_MENU",
    "CONTROL",
    "CONTROL_LEFT",
    "CONTROL_RIGHT",
    "CONVERT",
    "COPY",
    "CR_SEL",
    "CUT",
    "DELETE",
    "DIGIT_0",
    "DIGIT_1",
    "DIGIT_2",
    "DIGIT_3",
    "DIGIT_4",
    "DIGIT_5",
    "DIGIT_6",
    "DIGIT_7",
    "DIGIT_8",
    "DIGIT_9",
    "EISU",
    "EJECT",
    "END",
    "END_CALL",
    "ENTER",
    "EQUAL",
    "ERASE_EOF",
    "ESCAPE",
    "EXECUTE",
    "EX_SEL",
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
    "F12",
    "F13",
    "F14",
    "F15",
    "F16",
    "F17",
    "F18",
    "F19",
    "F20",
    "F21",
    "F22",
    "F23",
    "F24",
    "F25",
    "F26",
    "F27",
    "F28",
    "F29",
    "F30",
    "F31",
    "F32",
    "F33",
    "F34",
    "F35",
    "FINAL_MODE",
    "FIND",
    "FN",
    "FN_LOCK",
    "GO_BACK",
    "GO_HOME",
    "GROUP_FIRST",
    "GROUP_LAST",
    "GROUP_NEXT",
    "GROUP_PREVIOUS",
    "HANGUL_MODE",
    "HANJA_MODE",
    "HANKAKU",
    "HEADSET_HOOK",
    "HELP",
    "HIBERNATE",
    "HIRAGANA",
    "HIRAGANA_KATAKANA",
    "HOME",
    "HYPER",
    "INSERT",
    "JUNJA_MODE",
    "KANA_MODE",
    "KANJI_MODE",
    "KATAKANA",
    "KEY11",
    "KEY12",
    "KEY_A",
    "KEY_B",
    "KEY_C",
    "KEY_D",
    "KEY_E",
    "KEY_F",
    "KEY_G",
    "KEY_H",
    "KEY_I",
    "KEY_J",
    "KEY_K",
    "KEY_L",
    "KEY_M",
    "KEY_N",
    "KEY_O",
    "KEY_P",
    "KEY_Q",
    "KEY_R",
    "KEY_S",
    "KEY_T",
    "KEY_U",
    "KEY_V",
    "KEY_W",
    "KEY_X",
    "KEY_Y",
    "KEY_Z",
    "LAST_NUMBER_REDIAL",
    "LAUNCH_APPLICATION1",
    "LAUNCH_APPLICATION2",
    "LAUNCH_CALENDAR",
    "LAUNCH_CONTACTS",
    "LAUNCH_MAIL",
    "LAUNCH_MEDIA_PLAYER",
    "LAUNCH_MUSIC_PLAYER",
    "LAUNCH_PHONE",
    "LAUNCH_SCREEN_SAVER",
    "LAUNCH_SPREADSHEET",
    "LAUNCH_WEB_BROWSER",
    "LAUNCH_WEB_CAM",
    "LAUNCH_WORD_PROCESSOR",
    "LOG_OFF",
    "MAIL_FORWARD",
    "MAIL_REPLY",
    "MAIL_SEND",
    "MANNER_MODE",
    "MEDIA_CLOSE",
    "MEDIA_FAST_FORWARD",
    "MEDIA_PAUSE",
    "MEDIA_PLAY",
    "MEDIA_PLAY_PAUSE",
    "MEDIA_RECORD",
    "MEDIA_REWIND",
    "MEDIA_STOP",
    "MEDIA_TRACK_NEXT",
    "MEDIA_TRACK_PREVIOUS",
    "META",
    "META_LEFT",
    "META_RIGHT",
    "MICROPHONE_TOGGLE",
    "MICROPHONE_VOLUME_DOWN",
    "MICROPHONE_VOLUME_MUTE",
    "MICROPHONE_VOLUME_UP",
    "MINUS",
    "MODE_CHANGE",
    "NEW",
    "NEXT_CANDIDATE",
    "NON_CONVERT",
    "NOTIFICATION",
    "NUMPAD_0",
    "NUMPAD_1",
    "NUMPAD_2",
    "NUMPAD_3",
    "NUMPAD_4",
    "NUMPAD_5",
    "NUMPAD_6",
    "NUMPAD_7",
    "NUMPAD_8",
    "NUMPAD_9",
    "NUMPAD_ADD",
    "NUMPAD_BACKSPACE",
    "NUMPAD_CLEAR",
    "NUMPAD_CLEAR_ENTRY",
    "NUMPAD_COMMA",
    "NUMPAD_DECIMAL",
    "NUMPAD_DIVIDE",
    "NUMPAD_ENTER",
    "NUMPAD_EQUAL",
    "NUMPAD_HASH",
    "NUMPAD_MEMORY_ADD",
    "NUMPAD_MEMORY_CLEAR",
    "NUMPAD_MEMORY_RECALL",
    "NUMPAD_MEMORY_STORE",
    "NUMPAD_MEMORY_SUBTRACT",
    "NUMPAD_MULTIPLY",
    "NUMPAD_PAREN_LEFT",
    "NUMPAD_PAREN_RIGHT",
    "NUMPAD_STAR",
    "NUMPAD_SUBTRACT",
    "NUM_LOCK",
    "OPEN",
    "PAGE_DOWN",
    "PAGE_UP",
    "PASTE",
    "PAUSE",
    "PERIOD",
    "PLAY",
    "POWER",
    "POWER_OFF",
    "PREVIOUS_CANDIDATE",
    "PRINT",
    "PRINT_SCREEN",
    "PROCESS",
    "PROPS",
    "QUOTE",
    "REDO",
    "ROMAJI",
    "SAVE",
    "SCROLL_LOCK",
    "SELECT",
    "SEMICOLON",
    "SHIFT",
    "SHIFT_LEFT",
    "SHIFT_RIGHT",
    "SINGLE_CANDIDATE",
    "SLASH",
    "SOFT1",
    "SOFT2",
    "SOFT3",
    "SOFT4",
    "SPACE",
    "SPEECH_CORRECTION_LIST",
    "SPEECH_INPUT_TOGGLE",
    "SPELL_CHECK",
    "STANDBY",
    "SUPER",
    "SYMBOL",
    "SYMBOL_LOCK",
    "TAB",
    "TV",
    "TV_3D_MODE",
    "TV_ANTENNA_CABLE",
    "TV_AUDIO_DESCRIPTION",
    "TV_AUDIO_DESCRIPTION_MIX_DOWN",
    "TV_AUDIO_DESCRIPTION_MIX_UP",
    "TV_CONTENTS_MENU",
    "TV_DATA_SERVICE",
    "TV_INPUT",
    "TV_INPUT_COMPONENT1",
    "TV_INPUT_COMPONENT2",
    "TV_INPUT_COMPOSITE1",
    "TV_INPUT_COMPOSITE2",
    "TV_INPUT_HDMI1",
    "TV_INPUT_HDMI2",
    "TV_INPUT_HDMI3",
    "TV_INPUT_HDMI4",
    "TV_INPUT_VGA1",
    "TV_MEDIA_CONTEXT",
    "TV_NETWORK",
    "TV_NUMBER_ENTRY",
    "TV_POWER",
    "TV_RADIO_SERVICE",
    "TV_SATELLITE",
    "TV_SATELLITE_BS",
    "TV_SATELLITE_CS",
    "TV_SATELLITE_TOGGLE",
    "TV_TERRESTRIAL_ANALOG",
    "TV_TERRESTRIAL_DIGITAL",
    "TV_TIMER",
    "UNDO",
    "UNIDENTIFIED",
    "VOICE_DIAL",
    "WAKE_UP",
    "ZENKAKU",
    "ZENKAKU_HANKAKU",
    "ZOOM_IN",
    "ZOOM_OUT",
]
