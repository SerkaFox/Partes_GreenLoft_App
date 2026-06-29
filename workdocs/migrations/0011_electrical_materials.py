from django.db import migrations

MATERIALS = [
    # Cables unipolares
    ('Cable unipolar 1.5mm²', 'm'),
    ('Cable unipolar 2.5mm²', 'm'),
    ('Cable unipolar 4mm²', 'm'),
    ('Cable unipolar 6mm²', 'm'),
    ('Cable unipolar 10mm²', 'm'),
    ('Cable unipolar 16mm²', 'm'),
    ('Cable unipolar 25mm²', 'm'),
    # Mangueras
    ('Cable manguera 2x1.5mm²', 'm'),
    ('Cable manguera 3x1.5mm²', 'm'),
    ('Cable manguera 3x2.5mm²', 'm'),
    ('Cable manguera 3x4mm²', 'm'),
    ('Cable manguera 3x6mm²', 'm'),
    ('Cable manguera 5x2.5mm²', 'm'),
    ('Cable manguera 5x4mm²', 'm'),
    ('Cable libre de halógenos 2.5mm²', 'm'),
    ('Cable libre de halógenos 4mm²', 'm'),
    ('Cable apantallado 2x1.5mm²', 'm'),
    ('Cable RJ45 Cat6', 'm'),
    ('Cable coaxial RG6', 'm'),
    # Automáticos
    ('Automático 10A 1P', 'uds'),
    ('Automático 16A 1P', 'uds'),
    ('Automático 20A 1P', 'uds'),
    ('Automático 25A 1P', 'uds'),
    ('Automático 32A 1P', 'uds'),
    ('Automático 40A 1P', 'uds'),
    ('Automático 16A 2P', 'uds'),
    ('Automático 25A 2P', 'uds'),
    ('Automático 40A 2P', 'uds'),
    ('Automático 63A 2P', 'uds'),
    ('Automático 16A 3P', 'uds'),
    ('Automático 25A 3P', 'uds'),
    ('Automático 40A 3P', 'uds'),
    # Diferenciales
    ('Diferencial 25A 30mA 2P', 'uds'),
    ('Diferencial 40A 30mA 2P', 'uds'),
    ('Diferencial 63A 30mA 2P', 'uds'),
    ('Diferencial 25A 30mA 4P', 'uds'),
    ('Diferencial 40A 30mA 4P', 'uds'),
    ('Diferencial 63A 30mA 4P', 'uds'),
    ('Diferencial superinmunizado 40A 30mA 2P', 'uds'),
    ('Diferencial superinmunizado 40A 30mA 4P', 'uds'),
    # Cuadros eléctricos
    ('Cuadro eléctrico superficie 12 módulos', 'uds'),
    ('Cuadro eléctrico superficie 24 módulos', 'uds'),
    ('Cuadro eléctrico superficie 36 módulos', 'uds'),
    ('Cuadro eléctrico empotrable 12 módulos', 'uds'),
    ('Cuadro eléctrico empotrable 24 módulos', 'uds'),
    ('Cuadro eléctrico empotrable 36 módulos', 'uds'),
    # Cajas
    ('Caja de empalme 100x100mm IP55', 'uds'),
    ('Caja de empalme 150x150mm IP55', 'uds'),
    ('Caja de registro 200x200mm IP55', 'uds'),
    ('Caja de derivación IP65', 'uds'),
    ('Caja de mecanismo empotrar 1 elemento', 'uds'),
    ('Caja de mecanismo empotrar 2 elementos', 'uds'),
    ('Caja de mecanismo superficie', 'uds'),
    # Mecanismos
    ('Enchufe schuko superficie', 'uds'),
    ('Enchufe schuko empotrable', 'uds'),
    ('Base doble enchufe empotrable', 'uds'),
    ('Interruptor empotrable', 'uds'),
    ('Conmutador empotrable', 'uds'),
    ('Cruzamiento empotrable', 'uds'),
    ('Pulsador empotrable', 'uds'),
    ('Base enchufe 16A industrial', 'uds'),
    # Aislamiento y cinta
    ('Cinta aislante PVC negra', 'rollos'),
    ('Cinta aislante PVC roja', 'rollos'),
    ('Cinta aislante PVC azul', 'rollos'),
    ('Cinta aislante alta tensión', 'rollos'),
    ('Cinta autofundente', 'rollos'),
    ('Termorretráctil 6mm', 'm'),
    ('Termorretráctil 12mm', 'm'),
    ('Termorretráctil 25mm', 'm'),
    # Tubos corrugados
    ('Tubo corrugado M16', 'm'),
    ('Tubo corrugado M20', 'm'),
    ('Tubo corrugado M25', 'm'),
    ('Tubo corrugado M32', 'm'),
    ('Tubo corrugado M40', 'm'),
    ('Tubo rígido PVC M16', 'm'),
    ('Tubo rígido PVC M20', 'm'),
    ('Tubo rígido PVC M25', 'm'),
    ('Tubo metálico flexible 16mm', 'm'),
    ('Tubo metálico flexible 20mm', 'm'),
    # Canaletas
    ('Canaleta PVC 20x10mm', 'm'),
    ('Canaleta PVC 25x16mm', 'm'),
    ('Canaleta PVC 40x25mm', 'm'),
    ('Canaleta PVC 60x40mm', 'm'),
    ('Canaleta PVC 100x60mm', 'm'),
    ('Bandeja metálica perforada 100mm', 'm'),
    ('Bandeja metálica perforada 200mm', 'm'),
    ('Bandeja metálica perforada 300mm', 'm'),
    # Fijaciones y conectores
    ('Bridas nylon 200mm', 'cajas'),
    ('Bridas nylon 300mm', 'cajas'),
    ('Grapas plástico M16', 'cajas'),
    ('Grapas plástico M20', 'cajas'),
    ('Grapas plástico M25', 'cajas'),
    ('Taco nylon 6mm', 'cajas'),
    ('Taco nylon 8mm', 'cajas'),
    ('Clema 2.5mm²', 'cajas'),
    ('Clema 4mm²', 'cajas'),
    ('Clema 6mm²', 'cajas'),
    ('Clema 10mm²', 'cajas'),
    ('Wago 2 conductores 2.5mm²', 'cajas'),
    ('Wago 3 conductores 2.5mm²', 'cajas'),
    ('Wago 5 conductores 2.5mm²', 'cajas'),
    ('Punteras ferrule 1.5mm²', 'cajas'),
    ('Punteras ferrule 2.5mm²', 'cajas'),
    ('Punteras ferrule 4mm²', 'cajas'),
    ('Punteras ferrule 6mm²', 'cajas'),
    ('Prensaestopas PG11 (M16)', 'uds'),
    ('Prensaestopas PG13 (M20)', 'uds'),
    ('Prensaestopas PG16 (M25)', 'uds'),
    # Iluminación
    ('Luminaria LED panel 60x60cm 36W', 'uds'),
    ('Downlight LED 20W empotrable', 'uds'),
    ('Downlight LED 12W empotrable', 'uds'),
    ('Regleta LED 60cm', 'uds'),
    ('Regleta LED 120cm', 'uds'),
    ('Aplique LED exterior', 'uds'),
    ('Proyector LED exterior 50W', 'uds'),
    ('Sensor de movimiento 360°', 'uds'),
    ('Temporizador escalera', 'uds'),
    ('Interruptor crepuscular', 'uds'),
    # Otros
    ('Pasta de obra', 'kg'),
    ('Silicon transparente', 'uds'),
    ('Espiral plástica 16mm', 'm'),
    ('Canaleta UNEX 60x40mm', 'm'),
    ('Regleta conexión universal', 'uds'),
    ('ICP 10A 1P', 'uds'),
    ('ICP 25A 2P', 'uds'),
    ('Descargador de sobretensión', 'uds'),
    ('Relé temporizador', 'uds'),
    ('Contactor 16A 2NA', 'uds'),
    ('Contactor 25A 2NA', 'uds'),
]


def add_materials(apps, schema_editor):
    Material = apps.get_model('workdocs', 'Material')
    for name, unit in MATERIALS:
        Material.objects.get_or_create(name=name, defaults={'unit': unit})


def remove_materials(apps, schema_editor):
    pass  # don't delete on reverse — materials may be in use


class Migration(migrations.Migration):

    dependencies = [
        ('workdocs', '0010_taskmaterial_is_needed'),
    ]

    operations = [
        migrations.RunPython(add_materials, remove_materials),
    ]
