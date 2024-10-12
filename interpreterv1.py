from intbase import InterpreterBase, ErrorType
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
        for statement_node in func_node.dict['statements']:
            self.run_statement(statement_node)
        
    def run_statement(self, statement_node):
        if statement_node.elem_type == 'vardef':
            if statement_node.dict['name'] in self.variable_names:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {statement_node.dict['name']} defined more than once",
                )
            self.variable_names.append(statement_node.dict['name'])
        elif statement_node.elem_type == '=':
            self.do_assignment(statement_node)
        elif statement_node.elem_type == 'fcall':
            self.function_call(statement_node)
    
    def do_assignment(self, assignment_node):
        if assignment_node.dict['name'] not in self.variable_names:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {assignment_node.dict['expression'].dict['name']} not defined yet",
                    )
        if assignment_node.dict['expression'].elem_type == 'var':
            self.variable_name_to_value[assignment_node.dict['name']] = self.variable_name_to_value[assignment_node.dict['expression'].dict['name']]
        elif assignment_node.dict['expression'].elem_type == 'int':
            self.variable_name_to_value[assignment_node.dict['name']] = (int)(assignment_node.dict['expression'].dict['val'])
        elif assignment_node.dict['expression'].elem_type == 'string':
            self.variable_name_to_value[assignment_node.dict['name']] = assignment_node.dict['expression'].dict['val']
        elif assignment_node.dict['expression'].elem_type == '+':
            self.variable_name_to_value[assignment_node.dict['name']] = self.handle_expression(assignment_node.dict['expression'].dict['op1'], assignment_node.dict['expression'].dict['op2'], '+')
        elif assignment_node.dict['expression'].elem_type == '-':
            self.variable_name_to_value[assignment_node.dict['name']] = self.handle_expression(assignment_node.dict['expression'].dict['op1'], assignment_node.dict['expression'].dict['op2'], '-')
            
    def handle_expression(self, op1, op2, operation):
        if op1.elem_type == '+' or op1.elem_type == '-':
            if operation == '+':
                return self.handle_expression(op1.op1, op1.op2, op1.elem_type) + op2
            elif operation == '-':
                return self.handle_expression(op1.op1, op1.op2, op1.elem_type) - op2
        elif op2.elem_type == '+' or op2.elem_type == '-':
            if operation == '+':
                return op1 + self.handle_expression(op2.op1, op2.op2, op2.elem_type)
            elif operation == '-':
                return op1 - self.handle_expression(op2.op1, op2.op2, op2.elem_type)
        elif op1.elem_type == 'string' or op2.elem_type == 'string':
            super().error(
                    ErrorType.NAME_ERROR,
                    f"Unsupported operation (string)",
                )
        elif op1.elem_type == 'int' or op2.elem_type == 'int':
            if op1.elem_type == 'int':
                return self.handle_expression((int)(op1.dict['val']), op2, operation)
            return self.handle_expression(op1, (int)(op2.dict['val'], operation))
        elif op1.elem_type == 'var' or op2.elem_type == 'var':
            if op1.dict['name'] not in self.variable_names or op2.dict['name'] not in self.variable_names:
                    super().error(
                    ErrorType.NAME_ERROR,
                    f"variable doesn't exist",
                )
            if op1.dict['name'].isdigit() == False or op2.dict['name'].isdigit() == False:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"variable is of type string",
                )
            if op1.elem_type == 'var':
                return self.handle_expression(self.variable_name_to_value[op1.dict['name']], op2, operation)
            return self.handle_expression(op1, self.variable_name_to_value[op2.dict['name']], operation)
        elif type(op1) == int and type(op2) == int:
            if operation == '+':
                return op1 + op2
            return op1 - op2
        else:
            super().error(
                    ErrorType.NAME_ERROR,
                    f"Unsupported expression",
                )
    def function_call(self, function_node):
        if function_node.dict['name'] == 'print':
            self.handle_print(function_node.dict['args'])
        elif function_node.dict['name'] == 'inputi':
            return InterpreterBase.get_input()
        else:
            super().error(
                    ErrorType.NAME_ERROR,
                    f"function type {function_node.dict['name']} not supported",
                )
            
    def handle_print(self, argument_nodes):
        for argument in argument_nodes:
            if argument.elem_type == '+' or argument.elem_type == '-':
                InterpreterBase.output(argument.op1, argument.op2, argument.elem_type)
            elif argument.elem_type == 'var':
                InterpreterBase.output(self.variable_name_to_value[argument.dict['name']])
            elif argument.elem_type == 'int' or argument.elem_type == 'string':
                InterpreterBase.output(argument.dict['val'])
            else:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Cannot print the arguments",
                )