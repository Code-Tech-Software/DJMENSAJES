"""Textos sugeridos y descripción de plantillas para el editor de invitaciones."""

PLANTILLAS = [
    {
        'valor': 'elegante', 'nombre': 'Elegante',
        'descripcion': 'Papel marfil, detalles dorados y caligrafía clásica.',
    },
    {
        'valor': 'jardin', 'nombre': 'Jardín',
        'descripcion': 'Botánica y romántica, con hojas y acuarela.',
    },
    {
        'valor': 'moderna', 'nombre': 'Moderna',
        'descripcion': 'Minimalista, tipografía grande y bloques de color.',
    },
    {
        'valor': 'fiesta', 'nombre': 'Neón',
        'descripcion': 'Noche de fiesta con luces de neón y brillo.',
    },
]

FRASES = {
    'boda': [
        'Hay momentos en la vida que son especiales por sí solos, pero compartirlos con las personas que queremos los hace inolvidables.',
        'Con la bendición de Dios y de nuestros padres, tenemos el honor de invitarte a celebrar nuestra unión.',
        'Dos caminos se unen para formar uno solo. Nos encantaría que fueras parte de este día.',
    ],
    'quinse': [
        'Hoy cierro un capítulo lleno de sueños y abro otro lleno de ilusiones. Acompáñame a celebrar mis XV años.',
        'Con la bendición de Dios y el amor de mis padres, te invito a celebrar conmigo este día tan especial.',
    ],
    'bautizo': [
        'Con mucha alegría te invitamos a acompañarnos en el bautizo de nuestro pequeño.',
        'Un nuevo camino de fe comienza. Acompáñanos a celebrar este día bendecido.',
    ],
    'aniversario': [
        'Los años pasan y el amor crece. Celebra con nosotros este nuevo aniversario.',
    ],
    'graduacion': [
        'Después de años de esfuerzo llegó el gran día. ¡Celebra conmigo este logro!',
    ],
}

FRASES_GENERALES = [
    'Tu presencia es el mejor regalo. ¡Te esperamos para celebrar juntos!',
    'Prepárate para una noche inolvidable llena de música, risas y buenos momentos.',
]

AVISOS = [
    'Evento solo para adultos',
    'Favor de llegar 15 minutos antes',
    'Tu confirmación es muy importante para nosotros',
    'Pases intransferibles',
]


def frases_para(tipo_evento):
    return FRASES.get(tipo_evento, []) + FRASES_GENERALES
