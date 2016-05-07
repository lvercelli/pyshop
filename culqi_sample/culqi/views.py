from cartridge.shop.models import Order
from django.http.response import HttpResponse
from django.views.generic import View
from pyculqi import crear_venta


class OrderCreationView(View):

    def post(self, request):
        order_id = request.data.get('order_id')
        order = Order.objects.get(id=order_id)
        crear_venta(

        )
        return HttpResponse()