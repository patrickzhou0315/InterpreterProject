from intbase import InterpreterBase
from brewparse import parse_program

class Interpreter(InterpreterBase):

    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)   # call InterpreterBase's constructor
        self.variable_name_to_value = {}
        self.variable_names = []

    def run(self, program):
        # program is array of strings we want to interpret
        ast = parse_program(program)
        main_func_node = self.get_main_func_node(ast)
        self.run_func(main_func_node)

    def get_main_func_node(self, ast):
        for node in ast.dict['functions']:
            if node.dict['name'] == 'main':
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
            self.variable_definition(statement_node)
        elif statement_node.elem_type == '=':
            self.do_assignment(statement_node)
        elif statement_node.elem_type == 'fcall':
            self.function_call(statement_node)
    
    def variable_definition(self, statement_node):
        if statement_node.dict['name'] in self.variable_names:
            super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {statement_node.dict['name']} defined more than once",
                    )
        self.variable_names.append(statement_node.dict['name'])
        self.variable_name_to_value[statement_node.dict['name']] = None   

    def do_assignment(self, assignment_node):
        if assignment_node.dict['name'] not in self.variable_names:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Variable {assignment_node.dict['name']} not defined yet",
                    )
        self.variable_name_to_value[assignment_node.dict['name']] = self.evaluate_expression(assignment_node.dict['expression'])

    def evaluate_expression(self, expression_node):
        if expression_node.elem_type == 'var':
            if expression_node.dict['name'] not in self.variable_names:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"variable {expression_node.dict['name']} undefined"
                )
            return self.variable_name_to_value[expression_node.dict['name']]
        elif expression_node.elem_type == 'int':
            return int(expression_node.dict['val'])
        elif expression_node.elem_type == 'string':
            return expression_node.dict['val']
        elif expression_node.elem_type == '+' or expression_node.elem_type == '-':
            return self.handle_expression(expression_node.dict['op1'], expression_node.dict['op2'], expression_node.elem_type)
        elif expression_node.elem_type == 'fcall':
            return self.function_call(expression_node)

    def handle_expression(self, op1, op2, operation):

        # if the expression has expressions in it
        # if both sides are expressions
        if op1.elem_type in ['+', '-'] and op2.elem_type in ['+', '-']:
            if operation == '+':
                return self.handle_expression(op1.dict['op1'], op1.dict['op2'], op1.elem_type) + self.handle_expression(op2.dict['op1'], op2.dict['op2'], op2.elem_type)
            return self.handle_expression(op1.dict['op1'], op1.dict['op2'], op1.elem_type) - self.handle_expression(op2.dict['op1'], op2.dict['op2'], op2.elem_type)
        # if the expression is only on left side
        elif op1.elem_type in ['+', '-']:
            # recursively call expression thing on the expression
            if operation == '+':
                return self.handle_expression(op1.dict['op1'], op1.dict['op2'], op1.elem_type) + self.evaluate_expression(op2)
            elif operation == '-':
                return self.handle_expression(op1.dict['op1'], op1.dict['op2'], op1.elem_type) - self.evaluate_expression(op2)
        # if the expression is only on the right side
        elif op2.elem_type in ['+', '-']:
            if operation == '+':
                return self.evaluate_expression(op1) + self.handle_expression(op2.dict['op1'], op2.dict['op2'], op2.elem_type)
            elif operation == '-':
                return self.evaluate_expression(op1) - self.handle_expression(op2.dict['op1'], op2.dict['op2'], op2.elem_type)
        # if any of the operators are strings
        elif op1.elem_type == 'string' or op2.elem_type == 'string':
            super().error(
                    ErrorType.NAME_ERROR,
                    f"Unsupported operation (string concatenation when defining variables)",
                )
        # if any of the operators are variables
        # checked if any were strings or expressions already, operations can either be Value (ints) or variables
        
        elif op1.elem_type == 'var':
            temp_var1 = self.evaluate_expression(op1)
            temp_var2 = self.evaluate_expression(op2)
            if not (isinstance(temp_var1, int) and isinstance(temp_var2, int)):
                    super().error(
                    ErrorType.TYPE_ERROR,
                    f"Unsupported operation (string concatenation when defining variables)",
                )
            if operation == '+':
                return temp_var1 + temp_var2
            return temp_var1 - temp_var2
        
        elif op2.elem_type == 'var':
            temp_var1 = self.evaluate_expression(op1)
            temp_var2 = self.evaluate_expression(op2)
            if not (isinstance(temp_var1, int) and isinstance(temp_var2, int)):
                    super().error(
                    ErrorType.TYPE_ERROR,
                    f"Unsupported operation (string concatenation when defining variables)",
                )
            if operation == '+':
                return temp_var1 + temp_var2
            return temp_var1 - temp_var2
        
        # if both operators are ints
        elif op1.elem_type == 'int':
            if operation == '+':
                return int(op1.dict['val']) + self.evaluate_expression(op2)
            return int(op1.dict['val']) - self.evaluate_expression(op2)
        
        elif op2.elem_type == 'int':
            if operation == '+':
                return int(op2.dict['val']) + self.evaluate_expression(op1)
            return self.evaluate_expression(op1) - int(op2.dict['val'])
        else:
            super().error(
                    ErrorType.NAME_ERROR,
                    f"Unsupported expression",
                )
            
    def function_call(self, function_node):
        if function_node.dict['name'] == 'print':
            self.handle_print(function_node.dict['args'])
        elif function_node.dict['name'] == 'inputi':
            if function_node.dict['args'] != None:
                for argument in function_node.dict['args']:
                    InterpreterBase.output(self, str(self.evaluate_expression(argument)))
            return int(self.get_input())
        else:
            super().error(
                    ErrorType.NAME_ERROR,
                    f"function type {function_node.dict['name']} not supported",
                )
            
    def handle_print(self, argument_nodes):
        output_string = ""
        for argument in argument_nodes:
            output_string += str(self.evaluate_expression(argument))
        InterpreterBase.output(self, output_string)