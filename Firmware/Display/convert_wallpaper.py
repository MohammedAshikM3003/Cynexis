import os
from PIL import Image

def convert_png_to_lvgl_c(png_path, c_path):
    img = Image.open(png_path).convert('RGB')
    img = img.resize((320, 240), Image.Resampling.LANCZOS)
    width, height = img.size

    pixels = img.load()

    with open(c_path, 'w', encoding='utf-8') as f:
        f.write('#include <lvgl.h>\n\n')

        f.write('#ifndef LV_ATTRIBUTE_MEM_ALIGN\n')
        f.write('#define LV_ATTRIBUTE_MEM_ALIGN\n')
        f.write('#endif\n\n')

        f.write('LV_ATTRIBUTE_MEM_ALIGN const uint8_t cynexis_wallpaper_map[] = {\n')

        byte_count = 0
        lines = []
        current_line = []

        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                r5 = (r >> 3) & 0x1F
                g6 = (g >> 2) & 0x3F
                b5 = (b >> 3) & 0x1F
                rgb565 = (r5 << 11) | (g6 << 5) | b5

                low_byte = rgb565 & 0xFF
                high_byte = (rgb565 >> 8) & 0xFF

                current_line.append(f"0x{low_byte:02x},0x{high_byte:02x}")
                byte_count += 2

                if len(current_line) >= 12:
                    lines.append("  " + ",".join(current_line) + ",")
                    current_line = []

        if current_line:
            lines.append("  " + ",".join(current_line))

        f.write("\n".join(lines))
        f.write("\n};\n\n")

        f.write('const lv_img_dsc_t cynexis_wallpaper = {\n')
        f.write('  .header.always_zero = 0,\n')
        f.write('  .header.w = 320,\n')
        f.write('  .header.h = 240,\n')
        f.write('  .data_size = 320 * 240 * 2,\n')
        f.write('  .header.cf = LV_IMG_CF_TRUE_COLOR,\n')
        f.write('  .data = cynexis_wallpaper_map,\n')
        f.write('};\n')

    print(f"Successfully converted {png_path} to {c_path} ({byte_count} bytes)")

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    png_file = os.path.join(base_dir, 'cynexis_wallpaper_320x240.png')
    c_file = os.path.join(base_dir, 'src', 'ui', 'cynexis_wallpaper.c')
    convert_png_to_lvgl_c(png_file, c_file)
