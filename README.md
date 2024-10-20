# midilifx

*Use a Lifx light as a MIDI visualizer*

**WARNING: Can cause the light to flash different bright colors in rapid succession, which I've heard could be dangerous for some people.** 


## Disclaimer

This is a toy that I wrote for fun (what other uses could there be ?) because I love MIDI and wanted to play with an "internet of things" device.

I **only tested it on my secondhand Lifx Color 1000** light, but it should work for others.


## Quick start

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


## About

`midilifx` is a Python module/commandline tool that "translates" MIDI events to colors and such in order to visualize them with a Lifx light.

It is based on the [mido](https://github.com/mido/mido) and [aiolifx](https://github.com/aiolifx/aiolifx) libraries.

At startup, it creates a virtual MIDI port and connects to the first found Lifx light on your network (I only have one).

Then, when receiving events on the MIDI port, they are translated to light settings, as follows:

- Color depends on the note
- Saturation depends on the velocity
- Lightness depends on the octave
- Color temperature can be controlled with pitch
- Transition delay between color changes can be controlled with modulation control change events (and set with the `-t/--transition` commandline switch)

## Colors

I had to find a way to map MIDI notes to colors.

I figured some smarter people had probably already given some thought to the subject, so there goes Newton's color circle:

![](https://upload.wikimedia.org/wikipedia/commons/0/0a/Newton%27s_colour_circle.png)

(From Wikipedia)

It is definitely not the only way to do it, and not the most modern one either, but it works pretty well for my toy.
