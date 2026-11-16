# LibreNMS 26.11.0 review fixtures

These YAML files are unmodified copies of `resources/definitions/os_discovery/{gwd,nokia-isam,scalance}.yaml` from official LibreNMS commit `49d74d08e636521ceeb4d78b672ddec2a5ea8fdb`. They retain LibreNMS's GPL-3.0-or-later licence. See the repository's NOTICE.md.

GWD corrects powerRunStatus to Empty=1/warning, Power Off=2/critical and Power On=3/ok, and devFanAlarmStatus to Alarm=1/critical and Normal=5/ok. The explicit LibreNMS tables supply both labels and severity.

Nokia ISAM moves alarmCount to a count sensor. It no longer supplies a state table, so the reviewed baseline removes that definition.

SCALANCE fixes malformed YAML, allowing its supported state tables to import. The two power supply state names contain spaces and remain outside the current sensor type contract. Their `No explicit sensor type` omission is reviewed; no substitute identity is invented. The baseline retains the older syntax omission for historical input review.

Only the two GWD fingerprints and the removed Nokia definition change in the existing definition baseline. All other fingerprints remain intact.
