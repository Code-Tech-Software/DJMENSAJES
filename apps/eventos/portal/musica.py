"""Lo que pregunta el cuestionario musical: los momentos especiales según el tipo de evento y los géneros."""

# Momentos con canción especial por tipo de evento: (clave, cómo se le pregunta al cliente)
MOMENTOS = {
    'boda': [('entrada', 'Entrada de los novios'), ('primer_baile', 'Primer baile'), ('padres', 'Baile con los papás'),
             ('brindis', 'Brindis'), ('pastel', 'Pastel'), ('cierre', 'Última canción de la noche')],
    'quinse': [('entrada', 'Entrada de la quinceañera'), ('vals', 'Vals'), ('padres', 'Baile con papá'),
               ('sorpresa', 'Baile sorpresa'), ('brindis', 'Brindis'), ('cierre', 'Última canción de la noche')],
    'cumple': [('entrada', 'Entrada del festejado'), ('pastel', 'Mañanitas y pastel'), ('cierre', 'Última canción de la noche')],
    'bautizo': [('entrada', 'Entrada'), ('pastel', 'Pastel'), ('cierre', 'Última canción')],
    'graduacion': [('entrada', 'Entrada de la generación'), ('vals', 'Vals de graduación'), ('brindis', 'Brindis'),
                   ('cierre', 'Última canción de la noche')],
    'aniversario': [('entrada', 'Entrada de la pareja'), ('primer_baile', 'Baile de la pareja'), ('brindis', 'Brindis'),
                    ('cierre', 'Última canción de la noche')],
    'corporativo': [('entrada', 'Bienvenida'), ('reconocimientos', 'Reconocimientos'), ('cierre', 'Última canción')],
    'fiesta': [('entrada', 'Para abrir la pista'), ('hora_loca', 'Hora loca'), ('cierre', 'Última canción de la noche')],
    'otro': [('entrada', 'Entrada'), ('especial', 'Momento especial'), ('cierre', 'Última canción')],
}

# Para mostrar momentos guardados aunque después cambie el tipo de evento
ETIQUETAS = {clave: nombre for lista in MOMENTOS.values() for clave, nombre in lista}

GENEROS = [
    'Pop', 'Rock en español', 'Rock en inglés', 'Reguetón', 'Cumbia', 'Banda', 'Regional mexicano', 'Salsa',
    'Bachata', 'Merengue', 'Electrónica', 'Éxitos de los 80 y 90', 'Baladas', 'Jazz y lounge para la cena',
]


def momentos_de(tipo_evento):
    return MOMENTOS.get(tipo_evento, MOMENTOS['otro'])
