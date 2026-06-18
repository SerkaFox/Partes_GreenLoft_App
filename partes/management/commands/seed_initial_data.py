from django.core.management.base import BaseCommand

from partes.models import Proyecto, Tecnico, Vehiculo


WORKERS = [
    'Alejandro Guerrero', 'Alexander Cordova', 'Ander Relea', 'Andres Felipe', 'Angel Lopez',
    'Asier Romero', 'Borja Pinto', 'David Perez', 'Eduardo Barrios', 'Endika Robledo',
    'Enrique Fernandez', 'Eugenio Pecharroman', 'Felipe Tapia', 'Herman Lykasov',
    'Javier Vazquez', 'Jon Lobo', 'Jon San Juan', 'Jorge Gonzalez', 'Justino Gonzalez',
    'Kepa Caro', 'Kevin Yugueros', 'Koldobika Cabado', 'Leandro Gallego', 'Luis Requejo',
    'Odei Morillas', 'Rabii Ahalqui', 'Raul Torres', 'Ruben Gutierrez', 'Saul Jimenez',
    'Sergio Varela', 'Aritz Blanco', 'Asier ABejon', 'Sergei Svitkin',
]

VEHICLES = [
    '0319-HVM', '0411-KHN', '2313-LJM', '2319-FYC', '2467-GTB', '2586-HFS', '2622-DJG',
    '2700-HDL', '3113-FVK', '4097-KVH', '4216-GDV', '4948-GHX', '5140-FVZ', '5266-DNM',
    '5514-KLX', '5624-KLT', '5717-KBS', '5798-GLY', '5840-GLY', '6048-DLD', '6095-LDT',
    '6440-GFR', '6741-KNN', '6938-JYN', '7197-GMR', '7758-FBN', '7821-LRR', '9799-JCW',
    '0813-NZL furgo alquiler',
]

PROJECTS = [
    ('0 - GREEN', 'Greenloft', 'Trabajos varios'),
    ('PR-001', 'Cliente Demo', 'Obra Demo Norte'),
    ('PR-002', 'Cliente Demo', 'Obra Demo Sur'),
    ('PR-003', 'Cliente Industrial', 'Mantenimiento general'),
]


class Command(BaseCommand):
    help = 'Carga datos iniciales de trabajadores, vehículos y proyectos de forma idempotente.'

    def handle(self, *args, **options):
        for index, nombre in enumerate(WORKERS, start=1):
            Tecnico.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'activo': True,
                    'puede_ser_tecnico': True,
                    'puede_ser_companero': True,
                    'orden': index,
                },
            )
        for index, matricula in enumerate(VEHICLES, start=1):
            descripcion = 'furgo alquiler' if 'furgo alquiler' in matricula.lower() else ''
            Vehiculo.objects.update_or_create(
                matricula=matricula,
                defaults={'descripcion': descripcion, 'activo': True, 'orden': index},
            )
        for index, (codigo, cliente, obra) in enumerate(PROJECTS, start=1):
            Proyecto.objects.update_or_create(
                codigo=codigo,
                defaults={'cliente': cliente, 'obra': obra, 'activo': True, 'orden': index},
            )
        self.stdout.write(self.style.SUCCESS('Datos iniciales cargados.'))
