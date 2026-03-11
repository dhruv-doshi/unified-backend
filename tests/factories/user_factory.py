import factory
from factory import Faker
import uuid


class UserFactory(factory.Factory):
    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    name = Faker("name")
    email = Faker("email")
    password = "Password123!"
