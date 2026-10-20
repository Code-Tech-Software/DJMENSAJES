import json
from decimal import Decimal, InvalidOperation

from django import forms

from apps.colaboradores.models import Colaborador
from apps.core.modulos import modulos_de

from ..models import CategoriaServicio, Cliente, Cotizacion, Paquete, PaqueteServicio, Servicio, TipoEvento, orden_servicio

FORMATO_FECHA_HORA = '%Y-%m-%dT%H:%M'
MAX_CONCEPTOS = 60


class ServicioForm(forms.ModelForm):
    usa_agencia = True

    class Meta:
        model = Servicio
        fields = ['nombre', 'categoria', 'precio', 'unidad', 'activa', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Audio profesional', 'maxlength': 120}),
            'precio': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '0.00'}),
            'unidad': forms.RadioSelect,
            'activa': forms.RadioSelect,
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej. Bocinas, subwoofers y consola para 250 invitados'}),
        }

    def __init__(self, *args, agencia_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo se ofrecen los extras que incluye el plan de la agencia
        from apps.core.models import Agencia
        agencia = Agencia.objects.select_related('plan').filter(pk=agencia_id).first()
        modulos = modulos_de(agencia)
        ofrecidos = {'': True, Servicio.Activa.EN_VIVO: modulos['en_vivo'], Servicio.Activa.INVITACION: modulos['invitaciones']}
        self.fields['activa'].choices = [(v, n) for v, n in Servicio.Activa.choices if ofrecidos.get(v)]
        self.fields['activa'].required = False
        self.ofrece_extras = len(self.fields['activa'].choices) > 1
        if not self.ofrece_extras:
            self.fields.pop('activa')

    def clean_activa(self):
        return self.cleaned_data.get('activa') or ''

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio < 0:
            raise forms.ValidationError('No puede ser negativo.')
        return precio


class PaqueteForm(forms.ModelForm):
    """El paquete con sus servicios: cada servicio del catálogo se marca y lleva su cantidad (horas, piezas…)."""
    usa_agencia = True

    class Meta:
        model = Paquete
        fields = ['nombre', 'precio', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Boda Plata', 'maxlength': 120}),
            'precio': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '0.00'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej. Audio, iluminación y pista para tu boda'}),
        }

    def __init__(self, *args, agencia_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        actuales = {i.servicio_id: i.cantidad for i in self.instance.items.all()} if self.instance.pk else {}
        servicios = Servicio.objects.filter(agencia_id=agencia_id).filter(activo=True) | \
            Servicio.objects.filter(agencia_id=agencia_id, pk__in=list(actuales))
        self.opciones = []
        for s in sorted(servicios.distinct(), key=lambda s: (orden_servicio(s), s.orden, s.nombre.lower())):
            if self.is_bound:
                marcado = f's_{s.pk}' in self.data
                cantidad = self.data.get(f'c_{s.pk}') or '1'
            else:
                marcado = s.pk in actuales
                cantidad = f'{actuales.get(s.pk, Decimal("1")).normalize():f}'
            self.opciones.append({'servicio': s, 'marcado': marcado, 'cantidad': cantidad})
        self.elegidos = []

    def clean(self):
        datos = super().clean()
        self.elegidos = []
        for o in self.opciones:
            if not o['marcado']:
                continue
            try:
                cantidad = Decimal(str(o['cantidad']).replace(',', '.'))
            except InvalidOperation:
                cantidad = Decimal('0')
            if not Decimal('0') < cantidad <= Decimal('999'):
                raise forms.ValidationError(f'Revisa la cantidad de "{o["servicio"].nombre}".')
            self.elegidos.append((o['servicio'], cantidad))
        if not self.elegidos:
            raise forms.ValidationError('Elige al menos un servicio para el paquete.')
        if datos.get('precio') is not None and datos['precio'] < 0:
            self.add_error('precio', 'No puede ser negativo.')
        return datos

    def save(self, commit=True):
        paquete = super().save(commit=commit)
        if commit:
            paquete.items.all().delete()
            PaqueteServicio.objects.bulk_create([PaqueteServicio(paquete=paquete, servicio=s, cantidad=c) for s, c in self.elegidos])
        return paquete


def _decimal(valor, minimo, maximo, nombre):
    if valor in (None, ''):
        valor = 0
    try:
        numero = Decimal(str(valor).replace(',', '.')).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise forms.ValidationError(f'Revisa {nombre}.')
    if not minimo <= numero <= maximo:
        raise forms.ValidationError(f'Revisa {nombre}.')
    return numero


def leer_conceptos(texto, servicios, paquetes, requerido=False, precio_minimo=Decimal('0')):
    """
    Los conceptos que manda el navegador (JSON) ya validados, listos para ConceptoCotizacion/ConceptoEvento(**c).
    Solo se enlazan servicios y paquetes de la propia agencia (servicios y paquetes son {id: objeto} de ella).
    """
    try:
        crudos = json.loads(texto or '[]')
    except ValueError:
        raise forms.ValidationError('No se pudieron leer los conceptos; recarga la página.')
    if not isinstance(crudos, list):
        raise forms.ValidationError('No se pudieron leer los conceptos; recarga la página.')
    if requerido and not crudos:
        raise forms.ValidationError('Agrega al menos un servicio o paquete.')
    if len(crudos) > MAX_CONCEPTOS:
        raise forms.ValidationError(f'Máximo {MAX_CONCEPTOS} conceptos.')
    conceptos = []
    for i, c in enumerate(crudos, 1):
        if not isinstance(c, dict):
            raise forms.ValidationError('No se pudieron leer los conceptos; recarga la página.')
        descripcion = str(c.get('descripcion') or '').strip()[:160]
        if not descripcion:
            raise forms.ValidationError(f'El concepto {i} no tiene nombre.')
        servicio_id, paquete_id = c.get('servicio'), c.get('paquete')
        conceptos.append({
            'descripcion': descripcion,
            'detalle': str(c.get('detalle') or '').strip()[:400],
            'cantidad': _decimal(c.get('cantidad', 1), Decimal('0.01'), Decimal('9999'), f'la cantidad de "{descripcion}"'),
            'precio_unitario': _decimal(c.get('precio', 0), precio_minimo, Decimal('99999999'), f'el precio de "{descripcion}"'),
            'unidad': c.get('unidad') if c.get('unidad') in Servicio.Unidad.values else '',
            'servicio_id': servicio_id if servicio_id in servicios else None,
            'paquete_id': paquete_id if paquete_id in paquetes else None,
        })
    return conceptos


def conceptos_json(conceptos):
    """Conceptos guardados → lo que espera el editor del navegador."""
    return json.dumps([{
        'servicio': c.servicio_id, 'paquete': c.paquete_id, 'descripcion': c.descripcion, 'detalle': c.detalle,
        'cantidad': f'{c.cantidad.normalize():f}', 'unidad': c.unidad, 'precio': f'{c.precio_unitario:.2f}',
    } for c in conceptos])


class CotizacionForm(forms.ModelForm):
    """La cotización con sus conceptos; el cotizador manda los conceptos como JSON en un campo oculto."""
    conceptos = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Cotizacion
        fields = ['cliente', 'cliente_nombre', 'cliente_telefono', 'cliente_email', 'tipo_evento', 'nombre_evento', 'fecha_evento',
                  'duracion_horas', 'lugar', 'num_invitados', 'colaborador', 'descuento', 'anticipo_porcentaje', 'vigencia',
                  'condiciones', 'notas_internas']
        widgets = {
            'cliente': forms.HiddenInput(attrs={'data-cliente-id': ''}),
            'cliente_nombre': forms.TextInput(attrs={'placeholder': 'Busca en tu directorio o escribe uno nuevo', 'autocomplete': 'off',
                                                     'data-sugerencias': 'clientes'}),
            'cliente_telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'cliente_email': forms.EmailInput(attrs={'placeholder': 'cliente@correo.com'}),
            'nombre_evento': forms.TextInput(attrs={'placeholder': 'Ej. Boda Ana & Luis'}),
            'fecha_evento': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=FORMATO_FECHA_HORA),
            'duracion_horas': forms.NumberInput(attrs={'min': 1, 'max': 24, 'step': '0.5'}),
            'lugar': forms.TextInput(attrs={'placeholder': 'Ej. Jardín Las Palmas', 'autocomplete': 'off', 'data-sugerencias': 'lugares'}),
            'num_invitados': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Ej. 200'}),
            'descuento': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '0.00'}),
            'anticipo_porcentaje': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 5}),
            'vigencia': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'condiciones': forms.Textarea(attrs={'rows': 4}),
            'notas_internas': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Solo las ve tu equipo'}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        agencia_id = usuario.agencia_id if usuario else None
        self.fields['cliente'].queryset = Cliente.objects.visibles_para(usuario) if usuario else Cliente.objects.none()
        self.fields['tipo_evento'].choices = list(TipoEvento.choices)
        self.fields['fecha_evento'].input_formats = [FORMATO_FECHA_HORA, '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S']
        # Sub-agencia: solo de su agencia; quien pertenece a una sub-agencia cotiza a nombre de ella
        modulos = modulos_de(usuario.agencia if usuario and usuario.agencia_id else None)
        if not modulos['subagencias'] or (usuario and not usuario.ve_todo):
            self.fields.pop('colaborador')
        else:
            self.fields['colaborador'].queryset = Colaborador.objects.filter(estado=True, agencia_id=agencia_id)
            self.fields['colaborador'].empty_label = 'La agencia'
            self.fields['colaborador'].label = 'Cotiza'
        self._servicios = {s.pk: s for s in Servicio.objects.filter(agencia_id=agencia_id)}
        self._paquetes = {p.pk: p for p in Paquete.objects.filter(agencia_id=agencia_id)}
        if self.is_bound:
            self.conceptos_iniciales = self.data.get('conceptos') or '[]'
        else:
            self.conceptos_iniciales = conceptos_json(self.instance.conceptos.all()) if self.instance.pk else '[]'

    def clean_conceptos(self):
        return leer_conceptos(self.cleaned_data.get('conceptos'), self._servicios, self._paquetes, requerido=True)

    def clean(self):
        datos = super().clean()
        conceptos = datos.get('conceptos')
        descuento = datos.get('descuento')
        if descuento is not None and descuento < 0:
            self.add_error('descuento', 'No puede ser negativo.')
        elif conceptos and descuento:
            subtotal = sum(c['cantidad'] * c['precio_unitario'] for c in conceptos)
            if descuento > subtotal:
                self.add_error('descuento', 'El descuento no puede ser mayor al subtotal.')
        return datos


def datos_catalogo(agencia_id):
    """El catálogo activo para el cotizador (paquetes y servicios por categoría)."""
    nombres = dict(CategoriaServicio.choices)
    servicios = sorted(Servicio.objects.filter(agencia_id=agencia_id, activo=True),
                       key=lambda s: (orden_servicio(s), s.orden, s.nombre.lower()))
    paquetes = Paquete.objects.filter(agencia_id=agencia_id, activo=True).prefetch_related('items__servicio')
    return {
        'paquetes': [{'id': p.pk, 'nombre': p.nombre, 'precio': f'{p.precio:.2f}', 'detalle': p.detalle,
                      'descripcion': p.descripcion, 'ahorro': f'{p.ahorro:.2f}',
                      'activa': sorted({i.servicio.activa for i in p.items.all() if i.servicio.activa})} for p in paquetes],
        'servicios': [{'id': s.pk, 'nombre': s.nombre, 'precio': f'{s.precio:.2f}', 'unidad': s.unidad,
                       'unidad_txt': s.get_unidad_display(), 'detalle': s.descripcion, 'categoria': nombres[s.categoria],
                       'icono': s.icono, 'activa': [s.activa] if s.activa else []} for s in servicios],
    }
