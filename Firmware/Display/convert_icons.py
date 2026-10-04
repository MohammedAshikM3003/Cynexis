import os
from PIL import Image

try:
    Import("env")
except Exception:
    pass

def convert_icon_to_lvgl_c(png_path, c_path, h_path, var_name, target_size=(28, 28)):
    try:
        img = Image.open(png_path).convert('RGBA')
        if target_size and target_size != img.size:
            img = img.resize(target_size, Image.Resampling.LANCZOS)
        width, height = img.size
        pixels = img.load()
    except Exception as e:
        print(f"Error decoding {png_path}: {e}")
        return

    # Generate Header File
    with open(h_path, 'w', encoding='utf-8') as fh:
        fh.write(f'#ifndef {var_name.upper()}_H\n')
        fh.write(f'#define {var_name.upper()}_H\n\n')
        fh.write('#include <lvgl.h>\n\n')
        fh.write(f'extern const lv_img_dsc_t {var_name};\n\n')
        fh.write(f'#endif // {var_name.upper()}_H\n')

    # Generate Source C File
    with open(c_path, 'w', encoding='utf-8') as fc:
        fc.write(f'#include "{os.path.basename(h_path)}"\n\n')
        fc.write('#ifndef LV_ATTRIBUTE_MEM_ALIGN\n#define LV_ATTRIBUTE_MEM_ALIGN\n#endif\n\n')

        fc.write(f'LV_ATTRIBUTE_MEM_ALIGN const uint8_t {var_name}_map[] = {{\n')

        current_line = []
        lines = []

        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                r5 = (r >> 3) & 0x1F
                g6 = (g >> 2) & 0x3F
                b5 = (b >> 3) & 0x1F
                rgb565 = (r5 << 11) | (g6 << 5) | b5

                low_byte = rgb565 & 0xFF
                high_byte = (rgb565 >> 8) & 0xFF

                current_line.append(f"0x{low_byte:02x},0x{high_byte:02x},0x{a:02x}")

                if len(current_line) >= 6:
                    lines.append("  " + ",".join(current_line) + ",")
                    current_line = []

        if current_line:
            lines.append("  " + ",".join(current_line))

        fc.write("\n".join(lines))
        fc.write("\n};\n\n")

        fc.write(f'const lv_img_dsc_t {var_name} = {{\n')
        fc.write('  .header.always_zero = 0,\n')
        fc.write(f'  .header.w = {width},\n')
        fc.write(f'  .header.h = {height},\n')
        fc.write(f'  .data_size = {width * height * 3},\n')
        fc.write('  .header.cf = LV_IMG_CF_TRUE_COLOR_ALPHA,\n')
        fc.write(f'  .data = {var_name}_map,\n')
        fc.write('};\n')

    print(f"[PIL LANCZOS] Converted {png_path} -> {var_name} ({width}x{height}, {width * height * 3} bytes)")

def run_conversion():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, 'assets')
    out_dir = os.path.join(base_dir, 'src', 'ui', 'assets')
    os.makedirs(out_dir, exist_ok=True)

    icons = [
        ('rover.png', 'rover_icon', (28, 28)),
        ('control_glove.png', 'control_glove_icon', (28, 28)),
        ('status_glove.png', 'status_glove_icon', (28, 28)),
        ('arm.png', 'arm_icon', (28, 28)),
        ('camera.png', 'camera_icon', (28, 28)),
        ('app.png', 'app_icon', (28, 28)),
        ('assistant.png', 'assistant_icon', (28, 28)),
        ('demo.png', 'demo_icon', (28, 28)),
        ('gallery.png', 'gallery_icon', (28, 28)),
        ('alerts.png', 'alerts_icon', (28, 28)),
        ('emergency.png', 'emergency_icon', (28, 28)),
        ('settings.png', 'settings_icon', (28, 28)),
        ('logs.png', 'logs_icon', (28, 28)),
        ('calibration.png', 'calibration_icon', (28, 28)),
        ('keyboard.png', 'keyboard_icon', (28, 21)),
        ('trash.png', 'trash_icon', (22, 22)),
        ('keyboard_close.png', 'keyboard_close_icon', (16, 16)),
    ]

    for item in icons:
        png, var = item[0], item[1]
        sz = item[2] if len(item) > 2 else (28, 28)
        png_path = os.path.join(assets_dir, png)
        if os.path.exists(png_path):
            c_path = os.path.join(out_dir, f"{var}.c")
            h_path = os.path.join(out_dir, f"{var}.h")
            convert_icon_to_lvgl_c(png_path, c_path, h_path, var, target_size=sz)

if __name__ == '__main__':
    run_conversion()
