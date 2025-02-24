# StarStack AI

## Overview

StarStack AI is an opensource tool for creating star trail images that automates the laborious process using Machine Learning.

These days, it's hard to take an image of the night sky without capturing satellite streaks. Satellite streaks are lines that appear in night sky images as a result of light reflecting off satellites or space debris. These streaks are caused when a satellite crosses the sky during long-exposure photography, leaving a visible path in the captured image.

## Examples

Stacked Star Trail Image             |  Stacked Star Trail Image<br>w/ Satellite Streaks Removed
:-------------------------:|:-------------------------:
<img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/example_stack_with_streaks.jpg" alt="A stacked star trail image based on 250 long exposure photos" width="100%"/>  |  <img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/example_stack_with%20streaks_removed_and%20gaps_filled.jpg" alt="A stacked star trail image with satellite streaks removed" width="100%"/>

It can be difficult and tedious to remove satellite streaks from star trail images. If we try to remove streaks from a stacked image, photo editing software does a poor job preserving the natural arc of star trails. If we try to remove them from the inidividual frames that are used in the stack, the process is tedious because stacks are often composed of 100s of images so there may be 1000s of instances of streaks.

## Features and Workflow

#### Detect Streaks

The model will automatically flag streaks, indicated with green boxes.

<img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/workflow_auto_detect_streaks.png" alt="Auto-detect streaks" width="100%"/>

#### Stack images

Produce a composite image by taking the lightest pixels from each input image.

<img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/workflow_stack.png" alt="Auto-detect streaks" width="100%"/>

#### Manually flag unwanted regions

The streak detection model isn't perfect. We may need to manually flag additional streaks or other unwanted areas from images. When viewing a stacked image, Shift-Click will search for the input image containing the brightest pixels at that location. We flag an unwanted region by drawing a polygon (Right-Click points outlining the region). The manually flagged region is indicated in blue.

<img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/workflow_manually_flag_streaks.png" width="100%"/>

When all of the remaining streaks have been flagged, create a new stack.

#### Fill Gaps

Finally, we may notice some gaps in the star trails. These may be due to removing streaks or missing frames.

Gaps             |  Gaps Filled
:-------------------------:|:-------------------------:
<img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/workflow_fillgaps_A.png" width="100%"/>  |  <img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/workflow_fillgaps_B.png" alt="A stacked star trail image with satellite streaks removed" width="100%"/>

#### Complete

<img src="https://raw.githubusercontent.com/gkyle/startrails/refs/heads/main/docs/images/workflow_complete.png" width="100%"/>

## Usage

Clone this repo.

`cd src`

`pip install -r requirements.txt`

Generate a star trail stack:

`python main.py`

Note: Removing streaks is not a fast operation. It can take a few seconds per image, so removing streaks from a stack of hundreds of images will take several minutes.

## How does it work?

Star trail images are created by "stacking" a series of night sky images taken over a few minutes or hours ([See Wikipedia](https://en.wikipedia.org/wiki/Star_trail)). In the resulting composite image, each pixel is the MAX value of that pixel among the input images.

If an input image contains an unwanted region (eg. a satellite crosses a portion of the sky, leaving a bright streak), the region can be "blacked out" by drawing a black rectangle over it. When we stack the images, some other images in the stack will have brighter pixels in that region that will be included in the final "stacked" image. This is a process that can be done manually before stacking with other star trail stacking tools.

Startrails Stacker uses an object detection model to automatically identify streaks in the input images, then blacks out those streaks before composing the stack.

## Streak Detection

Streak detection is performed using a fine-tuned [YOLO](https://docs.ultralytics.com/) object detection model. These models typically work on small or down-scaled images (eg. 640x640). I found that models performed poorly when I downscaled training images. Instead, the current model is trained on a set of 512x512 cropped (unscaled) images and inference is performed using [SAHI](https://github.com/obss/sahi), which scans over the input image and performs inference in a moving 512x512 window. This is not fast, but performs quite well, especially on edge cases such as occlusion.

## Can I train my own model? Can I contribute?

Yes and yes. I've included the [dataset](https://github.com/gkyle/startrails/tree/main/data/512) that I used for training and notebooks for [working with labels and training here](https://github.com/gkyle/startrails/tree/main/training). Please feel free to make your own models.

I would like to improve the diversity of the dataset in this repo and welcome contributions. Only the 512x512 crops are needed. You can export your manually-flagged streaks directly from the app.
