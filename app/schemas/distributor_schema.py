from app.extensions import ma
from app.models.distributor import Distributor


class DistributorSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Distributor
        load_instance = True

    wilaya_name = ma.String(attribute="wilaya.name", dump_only=True)
