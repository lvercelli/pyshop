from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from cartridge.shop.forms import FormsetForm, DiscountForm
from cartridge.shop.models import Order, DiscountCode
from cartridge.shop.utils import make_choices
from cartridge.shop import checkout
from mezzanine.conf import settings
from datetime import date
from copy import copy


class OrderForm(FormsetForm, DiscountForm):
    step = forms.IntegerField(widget=forms.HiddenInput())
    same_billing_shipping = forms.BooleanField(required=False, initial=True,
        label=_("My delivery details are the same as my billing details"))
    remember = forms.BooleanField(required=False, initial=True,
        label=_("Remember my address for next time"))
    # card_name = forms.CharField(label=_("Cardholder name"))
    # card_type = forms.ChoiceField(label=_("Card type"),
    #     widget=forms.RadioSelect,
    #     choices=make_choices(settings.SHOP_CARD_TYPES))
    # card_number = forms.CharField(label=_("Card number"))
    # card_expiry_month = forms.ChoiceField(label=_("Card expiry month"),
    #     initial="%02d" % date.today().month,
    #     choices=make_choices(["%02d" % i for i in range(1, 13)]))
    # card_expiry_year = forms.ChoiceField(label=_("Card expiry year"))
    # card_ccv = forms.CharField(label=_("CCV"), help_text=_("A security code, "
    #     "usually the last 3 digits found on the back of your card."))

    class Meta:
        model = Order
        fields = ([f.name for f in Order._meta.fields if
                   f.name.startswith("billing_detail") or
                   f.name.startswith("shipping_detail")] +
                   ["additional_instructions", "discount_code"])

    def __init__(
            self, request, step, data=None, initial=None, errors=None,
            **kwargs):
        """
        Setup for each order form step which does a few things:

        - Calls OrderForm.preprocess on posted data
        - Sets up any custom checkout errors
        - Hides the discount code field if applicable
        - Hides sets of fields based on the checkout step
        - Sets year choices for cc expiry field based on current date
        """

        # ``data`` is usually the POST attribute of a Request object,
        # which is an immutable QueryDict. We want to modify it, so we
        # need to make a copy.
        data = copy(data)

        # Force the specified step in the posted data, which is
        # required to allow moving backwards in steps. Also handle any
        # data pre-processing, which subclasses may override.
        if data is not None:
            data["step"] = step
            data = self.preprocess(data)
        if initial is not None:
            initial["step"] = step

        super(OrderForm, self).__init__(
                request, data=data, initial=initial, **kwargs)
        self._checkout_errors = errors

        # Hide discount code field if it shouldn't appear in checkout,
        # or if no discount codes are active.
        settings.use_editable()
        if not (settings.SHOP_DISCOUNT_FIELD_IN_CHECKOUT and
                DiscountCode.objects.active().exists()):
            self.fields["discount_code"].widget = forms.HiddenInput()

        # Determine which sets of fields to hide for each checkout step.
        # A ``hidden_filter`` function is defined that's used for
        # filtering out the fields to hide.
        is_first_step = step == checkout.CHECKOUT_STEP_FIRST
        is_last_step = step == checkout.CHECKOUT_STEP_LAST
        is_payment_step = step == checkout.CHECKOUT_STEP_PAYMENT
        hidden_filter = lambda f: False
        if settings.SHOP_CHECKOUT_STEPS_SPLIT:
            if is_first_step:
                # Hide cc fields for billing/shipping if steps are split.
                hidden_filter = lambda f: f.startswith("card_")
            elif is_payment_step:
                # Hide non-cc fields for payment if steps are split.
                hidden_filter = lambda f: not f.startswith("card_")
        elif not settings.SHOP_PAYMENT_STEP_ENABLED:
            # Hide all cc fields if payment step is not enabled.
            hidden_filter = lambda f: f.startswith("card_")
        if settings.SHOP_CHECKOUT_STEPS_CONFIRMATION and is_last_step:
            # Hide all fields for the confirmation step.
            hidden_filter = lambda f: True
        for field in filter(hidden_filter, self.fields):
            self.fields[field].widget = forms.HiddenInput()
            self.fields[field].required = False

        # Set year choices for cc expiry, relative to the current year.
        year = now().year
        choices = make_choices(list(range(year, year + 21)))
        # self.fields["card_expiry_year"].choices = choices

    @classmethod
    def preprocess(cls, data):
        """
        A preprocessor for the order form data that can be overridden
        by custom form classes. The default preprocessor here handles
        copying billing fields to shipping fields if "same" checked.
        """
        if data.get("same_billing_shipping", "") == "on":
            for field in data:
                bill_field = field.replace("shipping_detail", "billing_detail")
                if field.startswith("shipping_detail") and bill_field in data:
                    data[field] = data[bill_field]
        return data

    def clean(self):
        """
        Raise ``ValidationError`` if any errors have been assigned
        externally, via one of the custom checkout step handlers.
        """
        if self._checkout_errors:
            raise forms.ValidationError(self._checkout_errors)
        return super(OrderForm, self).clean()