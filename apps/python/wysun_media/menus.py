"""The popup menus of the control bar: speed, subtitles, audio tracks, more actions and file information."""
from .controls import PopupMenu, clock
from .bar import speed_text


def _label(track):
    parts = [track.get('title'), track.get('lang')]
    text = ' · '.join(part for part in parts if part)
    return text or f"Pista {track['id']}"


def speed_menu(player):
    menu = PopupMenu(player).add_header('Velocidad de reproducción')
    for speed in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0):
        menu.add_item(speed_text(speed) + (' · Normal' if speed == 1.0 else ''), lambda s=speed: player.set_speed(s),
                      checked=abs(player.session.speed - speed) < .001)
    return menu


def subtitle_menu(player):
    session = player.session
    tracks = session.tracks('sub')
    menu = PopupMenu(player).add_header('Subtítulos')
    menu.add_item('Desactivados', lambda: session.select_subtitle(None), checked=not any(t.get('selected') for t in tracks))
    for track in tracks:
        menu.add_item(_label(track), lambda i=track['id']: session.select_subtitle(i), checked=bool(track.get('selected')))
    menu.add_separator()
    menu.add_item('Cargar archivo…', player.load_subtitle_file, symbol='folder_open')
    delay = session.props.get('sub-delay') or 0.0
    menu.add_item('Adelantar 0,1 s', lambda: session.shift_subtitles(-.1), detail=f'{delay:+.1f} s'.replace('.', ','), enabled=bool(tracks))
    menu.add_item('Retrasar 0,1 s', lambda: session.shift_subtitles(.1), enabled=bool(tracks))
    return menu


def audio_menu(player):
    session = player.session
    menu = PopupMenu(player).add_header('Pista de audio')
    for track in session.tracks('audio'):
        menu.add_item(_label(track), lambda i=track['id']: session.select_audio(i), checked=bool(track.get('selected')),
                      detail=track.get('codec', '').upper())
    return menu


def more_menu(player):
    session, menu = player.session, PopupMenu(player)
    if player.kind in ('video', 'audio'):
        a, b = session.ab_loop
        state = 'desactivado' if a is None else 'marcando B' if b is None else f'{clock(a)}–{clock(b)}'
        menu.add_item('Información', player.show_info, symbol='info')
        menu.add_item('Bucle del archivo', lambda: session.set_loop(not session.looping), checked=session.looping)
        menu.add_item('Bucle A-B', session.mark_loop, detail=state)
        if player.kind == 'video':
            menu.add_item('Fotograma anterior', lambda: session.step(-1), enabled=session.paused)
            menu.add_item('Fotograma siguiente', lambda: session.step(1), enabled=session.paused)
            menu.add_item('Guardar fotograma', player.save_frame, symbol='photo_camera')
        if player.bar.compact or player.mode == 'embedded':
            menu.add_separator()
            menu.add_item('Velocidad…', lambda: player.show_speed_menu(player.bar.more))
            if player.kind == 'video':
                menu.add_item('Subtítulos…', lambda: player.show_subtitle_menu(player.bar.more))
            if len(session.tracks('audio')) > 1:
                menu.add_item('Pista de audio…', lambda: player.show_audio_menu(player.bar.more))
    else:
        menu.add_item('Información', player.show_info, symbol='info')
        menu.add_item('Girar a la derecha', player.rotate, symbol='rotate_right')
        menu.add_item('Girar a la izquierda', lambda: player.rotate(-1), symbol='rotate_left')
        menu.add_item('Copiar imagen', player.copy_image, symbol='content_copy')
    menu.add_separator()
    menu.add_item('Copiar ruta', player.copy_path)
    menu.add_item('Mostrar en Files', player.reveal, symbol='folder_open')
    if player.mode == 'full':
        menu.add_item('Mover a la papelera', player.trash, symbol='delete')
    if player.extra_actions:
        menu.add_separator()
        for label, callback in player.extra_actions:
            menu.add_item(label, callback)
    return menu


def _size(count):
    value = float(count)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'.replace('.', ',')
        value /= 1024


def info_menu(player):
    source, session = player.source, player.session
    menu = PopupMenu(player).add_header('Información')
    if source is None:
        return menu
    menu.add_info('Archivo', source.name)
    menu.add_info('Tamaño', _size(source.size))
    if player.kind == 'image':
        frame = player._images.frame if player._images else None
        if frame is not None:
            menu.add_info('Formato', frame.format.upper())
            menu.add_info('Dimensiones', f'{frame.size.width()} × {frame.size.height()}')
            menu.add_info('Detalle cargado', f'{frame.scale * 100:.0f} %')
        return menu
    props = session.props
    params = props.get('video-params') or {}
    menu.add_info('Duración', clock(session.duration))
    if player.kind == 'video':
        menu.add_info('Resolución', f"{params.get('w', '—')} × {params.get('h', '—')}")
        menu.add_info('Códec de video', props.get('video-codec') or '—')
        menu.add_info('Decodificador', 'Software' if props.get('hwdec-current') in (None, 'no', '') else 'Hardware · ' + props['hwdec-current'])
        menu.add_info('Renderizador', {'opengl': 'OpenGL', 'software': 'Software'}[player.renderer])
        dropped = (props.get('frame-drop-count') or 0) + (props.get('vo-drop-frame-count') or 0) + (props.get('decoder-frame-drop-count') or 0)
        menu.add_info('Fotogramas perdidos', str(dropped))
    menu.add_info('Códec de audio', props.get('audio-codec-name') or '—')
    return menu
