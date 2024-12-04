from type_valuev4 import Value

class LazyExpr:
    def __init__(self, value=None, unknown_var=None, expr_ast=None):
        self.v = value
        self.uv = unknown_var
        self.ea = expr_ast

    def value(self):
        return self.v
    
    def unknown_var(self):
        return self.uv
    
    def expr_ast(self):
        return self.ea