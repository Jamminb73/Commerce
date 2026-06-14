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

# Clean quantity list for bulk orders without full cart mess
QUANTITY_CHOICES = [
    (1, '1 Target Location ($8.00)'),
    (2, '2 Target Locations ($16.00)'),
    (3, '3 Target Locations ($24.00)'),
    (4, '4 Target Locations ($32.00)'),
    (5, '5 Target Locations (🔥 Buy 4 Get 1 Free! - $32.00)'),
]

class ChamberRequestForm(forms.ModelForm):
    """Handles user-facing requests for custom chamber directory scrapes with volume scaling built-in."""
    
    state = forms.ChoiceField(
        choices=STATE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    chambers_count = forms.ChoiceField(
        choices=QUANTITY_CHOICES,
        initial=1,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_chambers_count'}),
        label="Number of Chambers/Cities to Target"
    )

    chamber_name = forms.CharField(
        required=False,  
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': '3', 
            'placeholder': 'e.g., Cobb County Chamber (Leave blank to let our team source the correct directory for you)'
        })
    )
    
    chamber_url = forms.CharField(
        required=False,  
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': '3', 
            'placeholder': 'Leave blank to let our data engine locate the primary membership indexing links automatically'
        })
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
        }

    def clean_state(self):
        """Forces the selected state code abbreviation to uppercase and strips extra spaces."""
        state = self.cleaned_data.get('state', '').upper().strip()
        if not state:
            raise forms.ValidationError("Please select a state from the list.")
        return state