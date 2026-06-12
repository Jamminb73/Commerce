from django import forms
from .models import ChamberRequest

# Definitive list of US State choices for clean database metrics
STATE_CHOICES = [
    ('', 'Select a State...'),
    ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'), 
    ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'), 
    ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'), 
    ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'), 
    ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'), 
    ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'), 
    ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'), 
    ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'), 
    ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'), 
    ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'), 
    ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'), 
    ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'), 
    ('WI', 'Wisconsin'), ('WY', 'Wyoming')
]

COUNT_CHOICES = [
    (1, 'Single Local Area / Chamber Target ($9.99)'),
    (5, 'Regional Bundle Package (Up to 5 Areas) ($49.00)'),
    (10, 'Expanded Regional Pack (Up to 10 Areas) ($99.00)'),
    (20, 'Enterprise Multi-Region / Full State (Custom Quote - $10/ch)'),
]

class ChamberRequestForm(forms.ModelForm):
    """Handles nationwide user-facing requests for custom chamber directory scrapes with tiered options."""
    
    state = forms.ChoiceField(
        choices=STATE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    chambers_count = forms.ChoiceField(
        choices=COUNT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_chambers_count'})
    )

    class Meta:
        model = ChamberRequest
        fields = ['user_email', 'chambers_count', 'state', 'city_or_region', 'chamber_name', 'chamber_url']
        widgets = {
            'user_email': forms.EmailInput(attrs={
                'class': 'form-control', 
                'placeholder': 'your@email.com'
            }),
            'city_or_region': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'e.g., Austin, Round Rock, Buda'
            }),
            'chamber_name': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': '3', 
                'placeholder': 'List the specific Chambers of Commerce (one per line or comma-separated)...'
            }),
            'chamber_url': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': '3', 
                'placeholder': 'Paste the direct directory links to each target (one per line)...'
            }),
        }

    def clean_state(self):
        """Forces the selected state code abbreviation to uppercase and strips extra spaces."""
        state = self.cleaned_data.get('state', '').upper().strip()
        if not state:
            raise forms.ValidationError("Please select a state from the list.")
        return state