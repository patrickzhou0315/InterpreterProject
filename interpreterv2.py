# Add to spec:
# - printing out a nil value is undefined

from env_v1 import EnvironmentManager
from type_valuev1 import Type, Value, create_value, get_printable
from intbase import InterpreterBase, ErrorType
from brewparse import parse_program


# Main interpreter class
class Interpreter(InterpreterBase):
    # constants
    BIN_OPS = {"+", "-", "*", "/"}
    UNARY_OPS = {"!", "neg"}
    COMP_OPS = {'==', '<', '<=', '>', '>=', '!=', '&&', '||'}
    scopes = []

    # methods
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.__setup_ops()

    # run a program that's provided in a string
    # usese the provided Parser found in brewparse.py to parse the program
    # into an abstract syntax tree (ast)
    def run(self, program):
        ast = parse_program(program)
        self.__set_up_function_table(ast)
        main_func = self.__get_func_by_name_args("main", 0)
        self.env = EnvironmentManager()
        self.scopes.append(self.env)
        self.scopes[-1].isFunction = True
        self.__run_statements(main_func.get("statements"))

    def __set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        for func_def in ast.get("functions"):
            self.func_name_to_ast[func_def.get("name"), len(func_def.get("args"))] = func_def

    def __get_func_by_name_args(self, name, args):
        if (name, args) not in self.func_name_to_ast:
            super().error(ErrorType.NAME_ERROR, f"Function {name} not found")
        return self.func_name_to_ast[(name, args)]
            
    def __run_statements(self, statements):
        # all statements of a function are held in arg3 of the function AST node
        for statement in statements:
            if self.trace_output:
                print(statement)
            if statement.elem_type == InterpreterBase.FCALL_NODE:
                self.__call_func(statement)
            elif statement.elem_type == "=":
                self.__assign(statement)
            elif statement.elem_type == InterpreterBase.VAR_DEF_NODE:
                self.__var_def(statement)
            elif statement.elem_type == InterpreterBase.FOR_NODE:
                val = self.__run_for(statement)
                if val is not None and val[0] is True:
                    return val
            elif statement.elem_type == InterpreterBase.IF_NODE:
                val = self.__run_if(statement)
                if val is not None and val[0] is True:
                    return val
            elif statement.elem_type == InterpreterBase.RETURN_NODE:
                if statement.get("expression") == None:
                    return (True, Value(Type.NONE, None))
                returned_expression = self.__eval_expr(statement.get("expression"))
                return (True, returned_expression)
        return (False, 0)

    def __run_for(self, for_node):
        self.__assign(for_node.get("init"))
        while (self.__eval_comp(for_node.get("condition")).value() is True):
            self.scopes.append(EnvironmentManager())
            value = self.__run_statements(for_node.get("statements"))
            if value is not None and value[0] is True:
                self.scopes.pop()
                return value
            self.scopes.pop()
            self.__assign(for_node.get("update"))

    def __run_if(self, if_node):
        if (self.__eval_expr(if_node.get("condition")).type() == Type.INT or self.__eval_expr(if_node.get("condition")).type() == Type.STRING):
            super().error(ErrorType.TYPE_ERROR, f"")

        elif (self.__eval_expr(if_node.get("condition")).value() == True ):
            self.scopes.append(EnvironmentManager())
            value = self.__run_statements(if_node.get("statements"))
            if value is not None and value[0] is True:
                self.scopes.pop()
                return value
            self.scopes.pop()
        
        elif (self.__eval_expr(if_node.get("condition")).value() == False ):
            if if_node.get("else_statements") is None:
                return None
            self.scopes.append(EnvironmentManager())
            value = self.__run_statements(if_node.get("else_statements"))
            if value is not None and value[0] is True:
                self.scopes.pop()
                return value
            self.scopes.pop()

        elif (self.__eval_comp(if_node.get("condition")).value()):
            self.scopes.append(EnvironmentManager())
            value = self.__run_statements(if_node.get("statements"))
            if value is not None and value[0] is True:
                self.scopes.pop()
                return value
            self.scopes.pop()
            # add what's supposed to happen if one of the statements had a return
        
        elif (self.__eval_comp(if_node.get("condition")).value() is False):
            if if_node.get("else_statements") is None:
                return None
            self.scopes.append(EnvironmentManager())
            value = self.__run_statements(if_node.get("else_statements"))
            if value is not None and value[0] is True:
                self.scopes.pop()
                return value
            self.scopes.pop()
        else:
            super().error(ErrorType.TYPE_ERROR, f"If statement not boolean expression")

    def __call_func(self, call_node):
        func_name = call_node.get("name")
        if func_name == "print":
            return self.__call_print(call_node)
        if func_name == "inputi":
            return self.__call_input(call_node)
        if func_name == "inputs":
            return self.__call_input(call_node)
        if self.__get_func_by_name_args(func_name, len(call_node.get("args"))) is not None:
            self.scopes.append(EnvironmentManager())
            function_used = self.__get_func_by_name_args(call_node.get("name"), len(call_node.get("args")))
            self.scopes[-1].isFunction = True
            # create all the variables for the new function arguments and assign them to what they were called with
            for (new_arg, old_arg) in zip(function_used.get("args"), call_node.get("args")):
                if not self.scopes[-1].create(new_arg.get("name"), self.__eval_expr(old_arg, -2)):
                    super().error(
                ErrorType.NAME_ERROR, f"Duplicate definition for variable"
                )
            returned = self.__run_statements(function_used.get("statements"))
            if returned is not None and returned[0] is True:
                self.scopes.pop()
                return returned[1]
            self.scopes.pop()
            return Value(Type.NONE, None)



        super().error(ErrorType.NAME_ERROR, f"Function {func_name} not found")

    def __call_print(self, call_ast):
        output = ""
        for arg in call_ast.get("args"):
            result = self.__eval_expr(arg)  # result is a Value object
            output = output + get_printable(result)
        super().output(output)
        return Value(Type.NONE, None)

    def __call_input(self, call_ast):
        args = call_ast.get("args")
        if args is not None and len(args) == 1:
            result = self.__eval_expr(args[0])
            super().output(get_printable(result))
        elif args is not None and len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter"
            )
        inp = super().get_input()
        if call_ast.get("name") == "inputi":
            return Value(Type.INT, int(inp))
        if call_ast.get("name") == "inputs":
            return Value(Type.STRING, str(inp))
        # we can support inputs here later

    def __assign(self, assign_ast, scope=-1):
        var_name = assign_ast.get("name")
        value_obj = self.__eval_expr(assign_ast.get("expression"))
        if not self.scopes[self.__find_which_previous_scope(var_name, scope)].set(var_name, value_obj):
            super().error(
                ErrorType.NAME_ERROR, f"Undefined variable {var_name} in assignment"
            )

    def __find_which_previous_scope(self, varname, scope=-1):
        if varname in self.scopes[scope].environment.keys():
            return scope
        for i in range(len(self.scopes)):
            if self.scopes[-(i+1)].checkisFunction() is False:
                val = self.scopes[-(i+1)].get(varname)
                if val is not None:
                    return (-(i+1))
            else:
                break
        if varname not in self.scopes[-(i+1)].environment.keys():
            super().error(ErrorType.NAME_ERROR, f"Variable {varname} not found")
        return -(i+1)

    def __var_def(self, var_ast, scope=-1):
        var_name = var_ast.get("name")
        if not self.scopes[scope].create(var_name, Value(Type.INT, 0)):
            super().error(
                ErrorType.NAME_ERROR, f"Duplicate definition for variable {var_name}"
            )

    def __eval_expr(self, expr_ast, scope=-1):
        if expr_ast.elem_type == InterpreterBase.INT_NODE:
            return Value(Type.INT, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.STRING_NODE:
            return Value(Type.STRING, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.NIL_NODE:
            return Value(Type.NONE, None)
        if expr_ast.elem_type == InterpreterBase.BOOL_NODE:
            return Value(Type.BOOL, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.VAR_NODE:
            var_name = expr_ast.get("name")
            return self.scopes[self.__find_which_previous_scope(var_name, scope)].get(var_name)
        if expr_ast.elem_type == InterpreterBase.FCALL_NODE:
            return self.__call_func(expr_ast)
        if expr_ast.elem_type in Interpreter.BIN_OPS:
            return self.__eval_op(expr_ast, scope)
        if expr_ast.elem_type in Interpreter.UNARY_OPS:
            return self.__eval_unary(expr_ast)
        if expr_ast.elem_type in Interpreter.COMP_OPS:
            return self.__eval_comp(expr_ast)

    def __eval_op(self, arith_ast, scope=-1):
        left_value_obj = self.__eval_expr(arith_ast.get("op1"), scope)
        right_value_obj = self.__eval_expr(arith_ast.get("op2"), scope)
        if left_value_obj.type() != right_value_obj.type():
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible types for {arith_ast.elem_type} operation",
            )
        if arith_ast.elem_type not in self.op_to_lambda[left_value_obj.type()]:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible operator {arith_ast.elem_type} for type {left_value_obj.type()}",
            )
        f = self.op_to_lambda[left_value_obj.type()][arith_ast.elem_type]
        return f(left_value_obj, right_value_obj)
    
    def __eval_unary(self, unary_ast):
        value_obj = self.__eval_expr(unary_ast.get("op1"))
        if unary_ast.elem_type not in self.op_to_lambda[value_obj.type()]:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible operator {unary_ast.elem_type} for type {value_obj.type()}",
            )
        f = self.op_to_lambda[value_obj.type()][unary_ast.elem_type]
        return f(value_obj)
    
    def __eval_comp(self, comp_ast):
        left_value_obj = self.__eval_expr(comp_ast.get("op1"))
        right_value_obj = self.__eval_expr(comp_ast.get("op2"))
        if comp_ast.elem_type not in self.op_to_lambda[left_value_obj.type()]:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible operator {comp_ast.elem_type} for type {left_value_obj.type()}",
            )
        f = self.op_to_lambda[left_value_obj.type()][comp_ast.elem_type]
        
        # if f(left_value_obj, right_value_obj).value() is not True and f(left_value_obj, right_value_obj).value() is not False:
        #     super().error(
        #         ErrorType.TYPE_ERROR,
        #         f"Incompatible operator {comp_ast.elem_type} for type {left_value_obj.type()}",
        #     )

        if left_value_obj.type() is not right_value_obj.type():
            if comp_ast.elem_type == '==':
                return Value(Type.BOOL, False)
            elif comp_ast.elem_type == '!=':
                return Value(Type.BOOL, True)
            else:
                
                super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible operator {comp_ast.elem_type} for type {left_value_obj.type()}",
            )
      
        return f(left_value_obj, right_value_obj)

    def __setup_ops(self):
        self.op_to_lambda = {}
        # set up operations on integers
        self.op_to_lambda[Type.INT] = {}
        # arithmetic operatoins
        self.op_to_lambda[Type.INT]["+"] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.INT]["-"] = lambda x, y: Value(
            x.type(), x.value() - y.value()
        )
        self.op_to_lambda[Type.INT]["*"] = lambda x, y: Value(
            x.type(), x.value() * y.value()
        )
        self.op_to_lambda[Type.INT]["/"] = lambda x, y: Value(
            x.type(), x.value() // y.value()
        )
        # unary operators
        self.op_to_lambda[Type.INT]['neg'] = lambda x: Value(
            x.type(), -1 * x.value()
        )
        # comparison operators
        self.op_to_lambda[Type.INT]['=='] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.INT]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        self.op_to_lambda[Type.INT]['<'] = lambda x, y: Value(
            Type.BOOL, x.value() < y.value()
        )
        self.op_to_lambda[Type.INT]["<="] = lambda x, y: Value(
            Type.BOOL, x.value() <= y.value()
        )
        self.op_to_lambda[Type.INT]['>'] = lambda x, y: Value(
            Type.BOOL, x.value() > y.value()
        )
        self.op_to_lambda[Type.INT][">="] = lambda x, y: Value(
            Type.BOOL, x.value() >= y.value()
        )

        # set up operations on booleans
        self.op_to_lambda[Type.BOOL] = {}
        # logical binary operators
        self.op_to_lambda[Type.BOOL]["||"] = lambda x, y: Value(
            x.type(), x.value() or y.value()
        )
        self.op_to_lambda[Type.BOOL]["&&"] = lambda x, y: Value(
            x.type(), x.value() and y.value()
        )
        # logical unary operators
        self.op_to_lambda[Type.BOOL]["!"] = lambda x: Value(
            x.type(), not x.value()
        )
        # comparison operators
        self.op_to_lambda[Type.BOOL]['=='] = lambda x, y: Value(
            x.type(), x.value() == y.value()
        )
        self.op_to_lambda[Type.BOOL]['!='] = lambda x, y: Value(
            x.type(), x.value() != y.value()
        )

        # set up operations on None
        self.op_to_lambda[Type.NONE] = {}
         # comparison operators
        self.op_to_lambda[Type.NONE]['=='] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.NONE]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

        # set up operations on strings
        self.op_to_lambda[Type.STRING] = {}

        # binary operators
        self.op_to_lambda[Type.STRING]["+"] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        #comparison operators
        self.op_to_lambda[Type.STRING]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.STRING]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )