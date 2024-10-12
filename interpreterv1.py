from intbase import InterpreterBase
from brewparse import parse_program

class Interpreter(InterpreterBase):
    variable_name_to_value = {}
    variable_names = []

    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)   # call InterpreterBase's constructor

    def run(self, program):
        # program is array of strings we want to interpret
        ast = parse_program(program)
        main_func_node = self.get_main_func_node(ast)
        self.run_func(main_func_node)

    def get_main_func_node(self, ast):
        for node in ast:
            if node.elem_type == 'program':
                return node
        super().error(
            ErrorType.NAME_ERROR,
            "No main() function was found",
        )
            
    def run_func(self, func_node):
        for statement_node in func_node.statements:
            self.run_statement(statement_node)
        
    def run_statement(self, statement_node):
        if statement_node.elem_type == 'vardef':
            self.variable_names.append(statement_node.name)
        elif statement_node.elem_type == '=':
            self.do_assignment(statement_node)
        elif statement_node.elem_type == 'fcall':
            self.function_call()
    
    def do_assignment(self, assignment_node):
        if assignment_node.expression.elem_type == 'var':
            if assignment_node.expression.dict['name'] not in self.variable_names:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {var_name} defined more than once",
                    )
            self.variable_name_to_value[assignment_node.dict['name']] = self.variable_name_to_value[assignment_node.expression.dict['name']]
