import os
import struct
import zlib

try:
    Import("env")
except Exception:
    pass

def decode_png_to_rgba(png_path):
    with open(png_path, 'rb') as f:
        data = f.read()

    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f"Not a valid PNG file: {png_path}")

    offset = 8
    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    idat_data = bytearray()

    while offset < len(data):
        if offset + 8 > len(data):
            break
        length, chunk_type = struct.unpack('>I4s', data[offset:offset+8])
        chunk_data = data[offset+8:offset+8+length]
        offset += 8 + length + 4  # +4 for CRC

        if chunk_type == b'IHDR':
            width, height, bit_depth, color_type, comp, filt, inter = struct.unpack('>IIBBBBB', chunk_data)
        elif chunk_type == b'IDAT':
            idat_data.extend(chunk_data)
        elif chunk_type == b'IEND':
            break

    decompressed = zlib.decompress(idat_data)

    bpp = 4 if color_type == 6 else (3 if color_type == 2 else 1)
    stride = width * bpp

    raw_pixels = bytearray(width * height * 4)

    def paeth_predictor(a, b, c):
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        elif pb <= pc:
            return b
        else:
            return c

    prev_row = bytearray(stride)
    src_offset = 0

    for y in range(height):
        filter_type = decompressed[src_offset]
        src_offset += 1
        curr_row = bytearray(decompressed[src_offset:src_offset+stride])
        src_offset += stride

        unfiltered_row = bytearray(stride)
        for i in range(stride):
            filt_val = curr_row[i]
            left = unfiltered_row[i - bpp] if i >= bpp else 0
            up = prev_row[i]
            up_left = prev_row[i - bpp] if i >= bpp else 0

            if filter_type == 0:
                recon = filt_val
            elif filter_type == 1:
                recon = (filt_val + left) & 0xFF
            elif filter_type == 2:
                recon = (filt_val + up) & 0xFF
            elif filter_type == 3:
                recon = (filt_val + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                recon = (filt_val + paeth_predictor(left, up, up_left)) & 0xFF
            else:
                recon = filt_val

            unfiltered_row[i] = recon

        prev_row = unfiltered_row

        for x in range(width):
            dst_idx = (y * width + x) * 4
            if color_type == 6:  # RGBA
                src_idx = x * 4
                raw_pixels[dst_idx:dst_idx+4] = unfiltered_row[src_idx:src_idx+4]
            elif color_type == 2:  # RGB
                src_idx = x * 3
                raw_pixels[dst_idx:dst_idx+3] = unfiltered_row[src_idx:src_idx+3]
                raw_pixels[dst_idx+3] = 255
            elif color_type == 0:  # Grayscale
                src_idx = x
                g = unfiltered_row[src_idx]
                raw_pixels[dst_idx:dst_idx+3] = bytes([g, g, g])
                raw_pixels[dst_idx+3] = 255

    return width, height, raw_pixels

# High-Quality Anti-Aliased Area Box Downsampling
def resize_rgba_box(src_pixels, src_w, src_h, dst_w, dst_h):
    if src_w == dst_w and src_h == dst_h:
        return src_pixels

    dst_pixels = bytearray(dst_w * dst_h * 4)

    for y in range(dst_h):
        src_y0 = int(y * src_h / dst_h)
        src_y1 = int((y + 1) * src_h / dst_h)
        if src_y1 <= src_y0: src_y1 = src_y0 + 1

        for x in range(dst_w):
            src_x0 = int(x * src_w / dst_w)
            src_x1 = int((x + 1) * src_w / dst_w)
            if src_x1 <= src_x0: src_x1 = src_x0 + 1

            r_sum, g_sum, b_sum, a_sum = 0, 0, 0, 0
            count = 0

            for sy in range(src_y0, min(src_y1, src_h)):
                for sx in range(src_x0, min(src_x1, src_w)):
                    idx = (sy * src_w + sx) * 4
                    r_sum += src_pixels[idx]
                    g_sum += src_pixels[idx+1]
                    b_sum += src_pixels[idx+2]
                    a_sum += src_pixels[idx+3]
                    count += 1

            dst_idx = (y * dst_w + x) * 4
            if count > 0:
                dst_pixels[dst_idx]   = int(r_sum / count)
                dst_pixels[dst_idx+1] = int(g_sum / count)
                dst_pixels[dst_idx+2] = int(b_sum / count)
                dst_pixels[dst_idx+3] = int(a_sum / count)

    return dst_pixels

def convert_icon_to_lvgl_c(png_path, c_path, h_path, var_name, target_size=(28, 28)):
    try:
        src_w, src_h, raw_pixels = decode_png_to_rgba(png_path)
        pixels = resize_rgba_box(raw_pixels, src_w, src_h, target_size[0], target_size[1])
        width, height = target_size
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
                idx = (y * width + x) * 4
                r, g, b, a = pixels[idx], pixels[idx+1], pixels[idx+2], pixels[idx+3]
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

    print(f"[BOX ANTI-ALIASED] Converted {png_path} -> {var_name} ({width}x{height}, {width * height * 3} bytes)")

def run_conversion():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, 'assets')
    out_dir = os.path.join(base_dir, 'src', 'ui', 'assets')
    os.makedirs(out_dir, exist_ok=True)

    icons = [
        ('rover.png', 'rover_icon'),
        ('control_glove.png', 'control_glove_icon'),
        ('status_glove.png', 'status_glove_icon'),
        ('arm.png', 'arm_icon'),
        ('camera.png', 'camera_icon'),
        ('app.png', 'app_icon'),
        ('assistant.png', 'assistant_icon'),
        ('demo.png', 'demo_icon'),
        ('gallery.png', 'gallery_icon'),
        ('alerts.png', 'alerts_icon'),
        ('emergency.png', 'emergency_icon'),
        ('settings.png', 'settings_icon'),
        ('logs.png', 'logs_icon'),
        ('calibration.png', 'calibration_icon'),
    ]

    for png, var in icons:
        png_path = os.path.join(assets_dir, png)
        if os.path.exists(png_path):
            c_path = os.path.join(out_dir, f"{var}.c")
            h_path = os.path.join(out_dir, f"{var}.h")
            convert_icon_to_lvgl_c(png_path, c_path, h_path, var, target_size=(28, 28))

run_conversion()
