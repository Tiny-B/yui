import sounddevice as sd, sys
for i, dev in enumerate(sd.query_devices()):
    if dev["max_input_channels"] > 0:
        print(f"{i}: {dev['name']}  (in_ch={dev['max_input_channels']})")
if sd.default.device[0] == -1:
    print("\n⚠️  No default input device (OS default is -1).", file=sys.stderr)
else:
    print("\nDefault input device index:", sd.default.device[0])