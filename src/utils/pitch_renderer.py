import base64
from src.config.config import Config

def render_pitch_html(text: str, position: int, color_line: str = "#8aa2b8") -> str:
    """
    Renders pitch accent using an embedded SVG image.
    This allows absolute control over the vertical positioning of the pitch line
    relative to the text, solving issues with HTML/CSS table vertical spacing.
    """
    config = Config()
    
    # Kana parsing fallback if not provided
    # text is the reading (e.g. "たまご")
    
    morae = []
    # Improved mora extraction (handles Hiragana and Katakana small letters)
    small_kana = "ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ"
    i = 0
    while i < len(text):
        char = text[i]
        nxt = text[i+1] if i+1 < len(text) else ""
        if nxt and nxt in small_kana: 
            morae.append(char + nxt)
            i += 2
        else:
            morae.append(char)
            i += 1
            
    num_morae = len(morae)
    if num_morae == 0: return text
    
    # Calculate pattern
    pattern = [False] * num_morae
    
    if position == 0: # Heiban: L H H ...
        for j in range(num_morae):
            if j == 0: pattern[j] = False
            else: pattern[j] = True
    elif position == 1: # Atamadaka: H L L ...
        pattern[0] = True
    else: # Nakadaka: L H ... H (at pos-1) L ...
        for j in range(num_morae):
            if j == 0: pattern[j] = False
            elif j < position: pattern[j] = True
            else: pattern[j] = False

    # --- SVG Generation ---
    # Dimensions
    SCALE = 20  # Internal resolution scaling factor
    
    # Variable Width Logic
    base_width_single = 16  # Tighten single chars (was 20)
    base_width_compound = 26 # Wider for combined (e.g. cha/shu)
    
    mora_widths = []
    for m in morae:
        if len(m) > 1:
            mora_widths.append(base_width_compound * SCALE)
        else:
            mora_widths.append(base_width_single * SCALE)

    char_height_base = 25
    char_height = char_height_base * SCALE
    
    # Calculate accumulated X positions
    x_positions = [0] * (num_morae + 1)
    current_x = 0
    for i, w in enumerate(mora_widths):
        x_positions[i] = current_x
        current_x += w
    x_positions[num_morae] = current_x
    
    total_content_width = x_positions[num_morae]
    
    # Add padding to prevent cutoff on right side
    padding_right = 5 * SCALE
    width = total_content_width + padding_right
    height = char_height
    
    # Display dimensions (CSS pixels) - assume 1 SCALE unit = 1px at base? 
    # Logic: char_width_base used to be 20. SCALED was 20*20.
    # We want final output in browser to roughly match base dimensions.
    # So display width should be (width / SCALE).
    disp_width = width / SCALE
    disp_height = height / SCALE
    
    # Font settings
    font_family = config.font_family or "sans-serif"
    font_size = 14 * SCALE
    
    # Colors
    text_color = config.color_highlight_reading
    
    # Coordinates (Scaled)
    y_line = 6 * SCALE      
    y_text = 20 * SCALE     
    drop_height = 4 * SCALE 
    stroke_width = 1.6 * SCALE # Slightly bolder
    
    # SVG Header
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    
    # 1. Draw Text
    # We place each mora centered in its slot
    svg += f'<g font-family="{font_family}" font-size="{font_size}" fill="{text_color}" text-anchor="middle">'
    for i, char in enumerate(morae):
        w = mora_widths[i]
        x_start = x_positions[i]
        x_center = x_start + (w / 2)
        svg += f'<text x="{x_center}" y="{y_text}">{char}</text>'
    svg += '</g>'
    
    # 2. Draw Lines
    # We draw lines for High segments and Drops
    svg += f'<path d="'
    path_d = ""
    
    for i in range(num_morae):
        is_high = pattern[i]
        
        if is_high:
            x_start = x_positions[i]
            x_end = x_positions[i+1]
            
            # Top Line for this mora
            path_d += f"M {x_start} {y_line} L {x_end} {y_line} "
            
            # Check for Drop (at end of this mora)
            if i == (position - 1):
                # Draw vertical drop
                path_d += f"M {x_end} {y_line} L {x_end} {y_line + drop_height} "

    svg += path_d
    svg += f'" stroke="{color_line}" stroke-width="{stroke_width}" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
    
    svg += '</svg>'
    
    # Encode
    b64_svg = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    img_tag = f'<img src="data:image/svg+xml;base64,{b64_svg}" width="{disp_width}" height="{disp_height}" style="vertical-align: bottom;" />'
    
    return img_tag
