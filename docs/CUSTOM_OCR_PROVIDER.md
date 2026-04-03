## How to create a custom OCR provider for weikipop

This guide explains how to create your own OCR provider for weikipop. You can integrate any OCR engine you prefer,
including offline models or web services.

## The basics: automatic discovery

weikipop automatically discovers and loads valid OCR providers. To be discovered, your provider must meet two
conditions:

1. **Directory:** it must be in its own subdirectory inside `/src/ocr/providers/`. For example:
   `/src/ocr/providers/my_cool_ocr/`.
2. **File:** it must have a `provider.py` file in that directory containing a class that inherits from `OcrProvider`.

The easiest way to start is to **copy `/src/ocr/providers/dummy/`**, rename it, and modify its contents.
The dummy provider is a fully commented template designed for this purpose.

## The contract: the `OcrProvider` interface

Your provider class must implement the contract defined in `src/ocr/interface.py` so it can communicate with the rest
of the application.

Your class must have:

* **NAME:** a unique, user-friendly string for your provider (e.g., `"My Cool OCR"`). This name is shown in the settings
  and tray icon menus.

* **scan(self, image: Image.Image) -> Optional[List[Paragraph]]:** this is the core method where all the work happens.
    * **input:** it receives a `PIL.Image.Image` object of the screen region to be scanned.
    * **output:** it must return:
        * a `List[Paragraph]` if ocr is successful (return an empty list `[]` if no text is found).
        * `None` if a critical error occurred.

## The data model: converting OCR output to weikipop's format

The main task of your `scan` method is to convert your OCR engine output into weikipop's standard data model.

* **BoundingBox(center_x, center_y, width, height):** represents the location and size of a piece of text.
    * **critical:** all coordinates and dimensions **must be normalized** to a `0.0` to `1.0` float range, relative to
      the input image's dimensions. `(0.0, 0.0)` is the top-left corner.

* **Word(text, separator, box):** represents a recognized string. `text` can be a full word (`"日本語"`) or a single
  character (`"日"`). weikipop hit scanning handles both cases. Providing single-character boxes often leads to more
  precise lookups.
    * `separator` is the character that follows the word (usually an empty string `""` for japanese).
    * `box` is a `BoundingBox` object for this specific word.

* **Paragraph(full_text, words, box, is_vertical):** a collection of `Word` objects that form a line or block of text.
    * `full_text` should be the complete, reconstructed text of the paragraph.
    * `is_vertical` must be set to `True` if the text is written top-to-bottom. if your ocr engine doesn't provide this,
      you can infer it from the paragraph's bounding box aspect ratio (`height > width`).

For example, if your OCR engine gives you an absolute pixel bounding box for a word: `{x: 50, y: 100, w: 200, h: 40}`
from an image that is `1000px` wide and `800px` high, convert it like this:

```python
# raw data from your ocr
raw_box = {'x': 50, 'y': 100, 'w': 200, 'h': 40}
img_width, img_height = 1000, 800

# conversion to normalized center_x, center_y, width, height
center_x = (raw_box['x'] + raw_box['w'] / 2) / img_width  # (50 + 100) / 1000 = 0.15
center_y = (raw_box['y'] + raw_box['h'] / 2) / img_height  # (100 + 20) / 800 = 0.15
width = raw_box['w'] / img_width  # 200 / 1000 = 0.2
height = raw_box['h'] / img_height  # 40 / 800 = 0.05

# create the weikipop object
meiki_box = BoundingBox(center_x, center_y, width, height)
```

## Activating your provider

Once your provider is implemented:

1. run weikipop.
2. right-click the tray icon.
3. go to ocr provider.
4. select the NAME of your new provider from the list.

weikipop will now use your class for all OCR operations.
