extends Control

var count := 0
var label: Label

func _ready() -> void:
    var center := CenterContainer.new()
    center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    add_child(center)
    var column := VBoxContainer.new()
    column.add_theme_constant_override("separation", 32)
    center.add_child(column)
    label = Label.new()
    label.text = "Godot no iPhone\n0"
    label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    label.add_theme_font_size_override("font_size", 44)
    column.add_child(label)
    var button := Button.new()
    button.text = "Somar +1"
    button.custom_minimum_size = Vector2(320, 100)
    button.add_theme_font_size_override("font_size", 32)
    button.pressed.connect(func():
        count += 1
        label.text = "Godot no iPhone\n%d" % count
    )
    column.add_child(button)
