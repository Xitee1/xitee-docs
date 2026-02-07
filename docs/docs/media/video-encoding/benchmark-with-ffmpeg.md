---
description: Simple ffmpeg benchmark test to compare video encoding speed across different machines using H.265/HEVC encoding.
---

# Benchmark with ffmpeg

This simple test lets you compare how fast your machine is at encoding videos.

Just use a sample video like this one:
`wget https://filesamples.com/samples/video/mkv/sample_1280x720_surfing_with_audio.mkv`

And start ffmpeg:
`ffmpeg -i sample_1280x720_surfing_with_audio.mkv -c:v libx265 -preset medium -crf 20 -an -f null -`

Sample output:
`encoded 4389 frames in 163.39s (26.86 fps), 3440.14 kb/s, Avg QP:23.81`
