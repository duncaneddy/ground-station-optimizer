import pyomo.kernel as pk


class Node(pk.block):
    """
    Generic node class representing an element in the MILP model.

    Args:
        id (str): Unique identifier for the node.
        obj (gsopt.model): Object being represented by the node.

    Note:
        The field name "children" is inherited from the pk.block class so it is not used here.
    """

    def __init__(self, **kwargs):
        super().__init__()
        self.obj = kwargs['obj']
        self.id = self.obj.id

    def dict(self):
        d = {
            "id:": self.id,
            "type": type(self).__name__,
        }

        return d


class BinaryNode(Node):
    """
    Node class representing a binary decision variable. Inherits from the Node class.

    Attributes:
        var (pyomo.kernel.variable): Binary decision variable
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.var = pk.variable(value=0, domain=pk.Binary)

    def dict(self):
        d = super().dict()

        # Add class specific attributes

        return d


class ProviderNode(BinaryNode):
    """
    Node class representing a provider. Inherits from the Node class.

    Attributes:
        var (pyomo.kernel.variable): binary decision variable
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def dict(self):
        d = super().dict()

        # Add class specific attributes

        return d


class StationNode(BinaryNode):
    """
    Node class representing a station. Inherits from the Node class.

    Attributes:
        var (pyomo.kernel.variable): binary decision variable
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.provider = kwargs['provider']

    def dict(self):
        d = super().dict()

        # Add class specific attributes

        return d


class ContactNode(BinaryNode):
    """
    Node class representing a contact. Inherits from the Node class.

    Attributes:
        var (pyomo.kernel.variable): binary decision variable
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.station = kwargs['station']
        self.provider = kwargs['provider']

    def dict(self):
        d = super().dict()

        # Add class specific attributes

        return d


class SatelliteNode(BinaryNode):
    """
    Node class representing a satellite. Inherits from the Node class.

    Attributes:
        var (pyomo.kernel.variable): binary decision variable
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def dict(self):
        d = super().dict()

        # Add class specific attributes

        return d