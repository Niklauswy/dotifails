"""Read only real system battery values; unavailable values remain None."""
from pathlib import Path


def battery_snapshot(root=Path('/sys/class/power_supply')):
    for supply in sorted(Path(root).glob('*')):
        def read(name):
            try:return (supply/name).read_text().strip()
            except OSError:return ''
        def number(name):
            try:return float(read(name))
            except ValueError:return None
        if read('type') != 'Battery' or read('scope') == 'Device':continue
        capacity=number('capacity')
        if capacity is not None and not 0<=capacity<=100:capacity=None
        status=read('status') or 'Unknown'
        energy=number('energy_now');full=number('energy_full');design=number('energy_full_design');power=number('power_now')
        voltage=number('voltage_now')
        if energy is None and voltage:
            charge=number('charge_now');charge_full=number('charge_full');charge_design=number('charge_full_design')
            energy=charge*voltage/1e6 if charge is not None else None
            full=charge_full*voltage/1e6 if charge_full is not None else None
            design=charge_design*voltage/1e6 if charge_design is not None else None
        if power is None and voltage:
            current=number('current_now');power=abs(current)*voltage/1e6 if current is not None else None
        hours=None
        if power and power>0 and energy is not None:
            remaining=full-energy if status=='Charging' and full else energy if status=='Discharging' else None
            if remaining is not None and remaining>=0:hours=remaining/power
        if hours is not None and hours>168:hours=None
        return dict(capacity=int(capacity) if capacity is not None else None,status=status,
                    watts=power/1e6 if power is not None else None,hours=hours,
                    health=min(100,full/design*100) if full and design else None,
                    cycles=number('cycle_count') if number('cycle_count') is not None and number('cycle_count')>=0 else None,name=supply.name)
    return dict(capacity=None,status='Unknown',watts=None,hours=None,health=None,cycles=None,name='')


def time_estimate(hours, charging=False):
    if hours is None:return 'Estimación de tiempo no disponible'
    minutes=max(1,round(hours*60));h,m=divmod(minutes,60)
    value=f'{h} h {m:02d} min' if h else f'{m} min'
    return ('Carga completa en ≈ ' if charging else 'Autonomía estimada ≈ ')+value
