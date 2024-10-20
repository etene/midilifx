# midilifx

*Use a Lifx light as a MIDI visualizer*

## Disclaimer

This is a toy that I wrote for fun (what other uses could there be ?). I only tested it on my secondhand Lifx Color 1000 light, but it should work for others.

## About

midilifx is a Python module/commandline tool that "translates" MIDI events to colors and such, to control a Lifx light.

It is based on the [mido](https://github.com/mido/mido) and [aiolifx](https://github.com/aiolifx/aiolifx) libraries.

At startup, it creates a virtual MIDI port and connects to the first found Lifx light on your network (I only have one).

Then, when receiving events on the MIDI port, they are "translated" to light settings, as follows:

- Color depends on the note
- Saturation depends on the velocity
- Lightness depends on the octave
- Color temperature can be controlled with pitch
- Transition delay between color changes can be controlled with modulation control change events

## Colors

Colors depend on the note, they are based on Newton's color circle:

![](https://upload.wikimedia.org/wikipedia/commons/0/0a/Newton%27s_colour_circle.png)

(From Wikipedia)

## Running

**TODO** pypi or something

For now:

- clone the repository
- create & activate a virtualenv
- install requirements
- run it, your light should be detected automatically:
```
$ python -m midilifx
[INFO] main: Opened virtual MIDI port 'midilifx'
[INFO] register: Found light at d0:73:d5:12:a1:7b
[INFO] midi_light: Connected to 'lampe cool' (LIFX Color 1000) at 192.168.94.130
[INFO] midi_light: Listening for MIDI events on channel(s) {0}
```

Now, you have to connect a MIDI source to the virtual `midilfix` port. I use `qpwgraph` for this and connect the MIDI Through port to it.

Then, start playing a MIDI and you should see the light change colors based on the MIDI notes. I use `mido-play` for this.

Of course, you can also use a MIDI keyboard or any other MIDI note source.

**note**: `midilifx` only plays notes from the first MIDI channel by default. The selected channed can be changed with the `-c/--channels` switch. It is not recommended to use too many channels at the same time, the result would probably be confusing.
