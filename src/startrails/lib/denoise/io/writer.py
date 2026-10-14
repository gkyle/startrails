"""Compatibility adapter for the shared image writer."""
from startrails.lib.image_io import imwrite


class ImageWriter:
    @classmethod
    def write(cls, data, filepath, compression="deflate", quality=95, **kwargs):
        return imwrite(filepath, data, convertBGR=True, quality=quality,
                       compression=compression.lower() != "none",
                       optimize=True, tiff_uint8_as_uint16=True, eight_bit=True)
