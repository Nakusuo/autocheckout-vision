import xml.etree.ElementTree as ET

from mltools.labelstudio import label_config


def test_one_label_per_sku_sorted():
    root = ET.fromstring(label_config({"TAKIS", "AGUA", "COLA"}))
    labels = [el.get("value") for el in root.iter("Label")]
    assert labels == ["AGUA", "COLA", "TAKIS"]


def test_rectangle_labels_point_to_image():
    root = ET.fromstring(label_config(["AGUA"]))
    rect = root.find("RectangleLabels")
    image = root.find("Image")
    assert rect.get("toName") == image.get("name") == "image"
    assert image.get("value") == "$image"


def test_values_are_escaped():
    root = ET.fromstring(label_config(['RARO"<&>']))
    assert [el.get("value") for el in root.iter("Label")] == ['RARO"<&>']
