import copy
from enum import Enum

from brewparse import parse_program
from env_v2 import EnvironmentManager
from intbase import InterpreterBase, ErrorType
from type_valuev2 import Type, Value, create_value, get_printable


class ExecStatus(Enum):
    CONTINUE = 1
    RETURN = 2


# Main interpreter class
class Interpreter(InterpreterBase):
    # constants
    NIL_VALUE = create_value(InterpreterBase.NIL_DEF)
    TRUE_VALUE = create_value(InterpreterBase.TRUE_DEF)
    BIN_OPS = {"+", "-", "*", "/", "==", "!=", ">", ">=", "<", "<=", "||", "&&"}
    PRIMITIVES = [Type.INT, Type.BOOL, Type.STRING]

    # methods
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.__setup_ops()
        self.structs = {}

    # run a program that's provided in a string
    # usese the provided Parser found in brewparse.py to parse the program
    # into an abstract syntax tree (ast)
    def run(self, program):
        ast = parse_program(program)
        self.__parse_structs(ast)
        self.__set_up_function_table(ast)
        self.env = EnvironmentManager()
        self.__call_func_aux("main", [])

    def __parse_structs(self, program_node):
        for struct_node in program_node.get("structs"):
            struct_name = struct_node.get("name")
            if struct_name in self.structs:
                super.error(
                    ErrorType.NAME_ERROR, 
                    f"Duplicate Struct Definition for: {struct_name}"
                )
            fields = {}
            for field_node in struct_node.get("fields"):
                field_type = field_node.get("var_type")
                if field_type not in self.PRIMITIVES:
                    if field_type not in self.structs:
                        if field_type != struct_name:
                            super.error(
                            ErrorType.NAME_ERROR, 
                            f"Duplicate Struct Definition for: {struct_name}"
                            )
                fields[field_node.get("name")] = field_node.get("var_type")
            self.structs[struct_name] = fields

    def __set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        for func_def in ast.get("functions"):
            func_name = func_def.get("name")
            num_params = len(func_def.get("args"))
            if func_name not in self.func_name_to_ast:
                self.func_name_to_ast[func_name] = {}
            self.func_name_to_ast[func_name][num_params] = func_def

    def __get_func_by_name(self, name, num_params):
        if name not in self.func_name_to_ast:
            super().error(ErrorType.NAME_ERROR, f"Function {name} not found")
        candidate_funcs = self.func_name_to_ast[name]
        if num_params not in candidate_funcs:
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {name} taking {num_params} params not found",
            )
        return candidate_funcs[num_params]

    def __run_statements(self, statements):
        self.env.push_block()
        for statement in statements:
            if self.trace_output:
                print(statement)
            status, return_val = self.__run_statement(statement)
            if status == ExecStatus.RETURN:
                self.env.pop_block()
                return (status, return_val)

        self.env.pop_block()
        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __run_statement(self, statement):
        status = ExecStatus.CONTINUE
        return_val = None
        if statement.elem_type == InterpreterBase.FCALL_NODE:
            self.__call_func(statement)
        elif statement.elem_type == "=":
            self.__assign(statement)
        elif statement.elem_type == InterpreterBase.VAR_DEF_NODE:
            self.__var_def(statement)
        elif statement.elem_type == InterpreterBase.RETURN_NODE:
            status, return_val = self.__do_return(statement)
        elif statement.elem_type == Interpreter.IF_NODE:
            status, return_val = self.__do_if(statement)
        elif statement.elem_type == Interpreter.FOR_NODE:
            status, return_val = self.__do_for(statement)

        return (status, return_val)
    
    def __call_func(self, call_node):
        func_name = call_node.get("name")
        actual_args = call_node.get("args")
        return self.__call_func_aux(func_name, actual_args)

    def __call_func_aux(self, func_name, actual_args):
        if func_name == "print":
            return self.__call_print(actual_args)
        if func_name == "inputi" or func_name == "inputs":
            return self.__call_input(func_name, actual_args)

        func_ast = self.__get_func_by_name(func_name, len(actual_args))
        formal_args = func_ast.get("args")
        if len(actual_args) != len(formal_args):
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {func_ast.get('name')} with {len(actual_args)} args not found",
            )

        # first evaluate all of the actual parameters and associate them with the formal parameter names
        args = {}

        for formal_ast, actual_ast in zip(formal_args, actual_args):
            formal_arg_type = formal_ast.get("var_type")
            actual_arg_type = actual_ast.get("var_type")
            result = self.__eval_expr(actual_ast)
            result = self.__coerce_value(actual_arg_type, result)
            result = self.__coerce_value(formal_arg_type, result)

            # if the thing being passed through isn't a struct
            if formal_arg_type not in self.structs:

                # if the thing being passed through isn't a primitive
                if formal_arg_type not in self.PRIMITIVES:
                    super().error(
                        ErrorType.TYPE_ERROR,
                        f"Invalid Types called with function: formal type {formal_arg_type} and actual argument {actual_arg_type}"
                    )
                # the argument passed through is a primitive, so make a copy of it to pass by value
                result = copy.copy(result)
            arg_name = formal_ast.get("name")
            args[arg_name] = result

        # then create the new activation record 
        self.env.push_func()
        # and add the formal arguments to the activation record
        for arg_name, value in args.items():
          self.env.create(arg_name, value)
        return_type = func_ast.get("return_type")
        _, return_val = self.__run_statements(func_ast.get("statements"))
        self.env.pop_func()

        # if it returns nothing and the return type indicates that it should return something
        if return_val == Interpreter.NIL_VALUE and return_type != Interpreter.VOID_DEF:
            return self.get_default_value(return_type)
        if return_val == Interpreter.NIL_VALUE and return_type == Interpreter.VOID_DEF:
            return return_val
        return_val = self.__coerce_value(return_type, return_val)
        return return_val
    
    def __coerce_value(self, coercer_type, coercee):
        if coercer_type == Type.BOOL and coercee.type() == Type.INT:
            if coercee.value() == 0:
                return Value(Type.BOOL, False)
            return Value(Type.BOOL, True)
        if coercer_type != coercee.type():
            super().error(
                ErrorType.TYPE_ERROR,
                f"Cannot coerce type {coercee.type} into {coercer_type}"
            )
        return coercee

    def __call_print(self, args):
        output = ""
        for arg in args:
            result = self.__eval_expr(arg)  # result is a Value object
            output = output + get_printable(result)
        super().output(output)
        return Interpreter.NIL_VALUE

    def __call_input(self, name, args):
        if args is not None and len(args) == 1:
            result = self.__eval_expr(args[0])
            super().output(get_printable(result))
        elif args is not None and len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter"
            )
        inp = super().get_input()
        if name == "inputi":
            return Value(Type.INT, int(inp))
        if name == "inputs":
            return Value(Type.STRING, inp)

    def __assign(self, assign_ast):
        var_name = assign_ast.get("name")
        value_obj = self.__eval_expr(assign_ast.get("expression"))
        if '.' in var_name:
            struct_var = var_name.split('.')
            root_var_name = struct_var[0]
            struct = self.env.get(root_var_name)
            if struct is None:
                super().error(
                    ErrorType.NAME_ERROR, f"Undefined struct variable {root_var_name}"
                )
            current = struct
            for field_name in struct_var[1:-1]:
                if field_name not in current.value().keys():
                    super().error(
                        ErrorType.NAME_ERROR, f"field {field_name} does not exist"
                    )
                current = current.value().get(field_name)
                if current is None:
                    super().error(
                        ErrorType.NAME_ERROR, f"field {field_name} is undefined"
                    )
            final_field = struct_var[-1]
            if final_field not in current.value().keys():
                super().error(ErrorType.NAME_ERROR, f"Field {field_name} does not exist in {root_var_name}")
            assigned_value = self.__coerce_value(current.value().get(final_field).type(), value_obj)
            current.value()[final_field] = assigned_value

        else:
            if not self.env.set(var_name, value_obj):
                super().error(
                    ErrorType.NAME_ERROR, f"Undefined variable {var_name} in assignment"
                )
    
    def __var_def(self, var_ast):
        var_name = var_ast.get("name")
        var_type = var_ast.get("var_type")
        default_value = self.get_default_value(var_type)
        if not self.env.create(var_name, default_value):
            super().error(
                ErrorType.NAME_ERROR, f"Duplicate definition for variable {var_name}"
            )

    def __eval_expr(self, expr_ast):
        if expr_ast.elem_type == InterpreterBase.NIL_NODE:
            return Interpreter.NIL_VALUE
        if expr_ast.elem_type == InterpreterBase.INT_NODE:
            return Value(Type.INT, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.STRING_NODE:
            return Value(Type.STRING, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.BOOL_NODE:
            return Value(Type.BOOL, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.VAR_NODE:
            var_name = expr_ast.get("name")
            if '.' in var_name:
                struct_var = var_name.split('.')
                root_var_name = struct_var[0]
                struct = self.env.get(root_var_name)
                if struct is None:
                    super().error(
                        ErrorType.NAME_ERROR, f"Undefined struct variable {root_var_name}"
                    )
                current = struct
                for field_name in struct_var[1:-1]:
                    if field_name not in current.value().keys():
                        super().error(
                            ErrorType.NAME_ERROR, f"field {field_name} does not exist"
                        )
                    current = current.value().get(field_name)
                    if current is None:
                        super().error(
                            ErrorType.NAME_ERROR, f"field {field_name} is undefined"
                        )
                final_field = struct_var[-1]
                if final_field not in current.value().keys():
                    super().error(ErrorType.NAME_ERROR, f"Field {field_name} does not exist in {root_var_name}")
                return current.value().get(final_field).value()
            else:
                val = self.env.get(var_name)
                if val is None:
                    super().error(ErrorType.NAME_ERROR, f"Variable {var_name} not found")
                return val
        if expr_ast.elem_type == InterpreterBase.FCALL_NODE:
            return self.__call_func(expr_ast)
        if expr_ast.elem_type in Interpreter.BIN_OPS:
            return self.__eval_op(expr_ast)
        if expr_ast.elem_type == Interpreter.NEG_NODE:
            return self.__eval_unary(expr_ast, Type.INT, lambda x: -1 * x)
        if expr_ast.elem_type == Interpreter.NOT_NODE:
            return self.__eval_unary(expr_ast, Type.BOOL, lambda x: not x)
        if expr_ast.elem_type == Interpreter.NEW_NODE:
            return self.__execute_new(expr_ast.get("var_type"))
        
    def __execute_new(self, struct_name):
        if struct_name not in self.structs:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Undefined Struct Type: {struct_name}"
            )
        struct_fields = self.structs[struct_name]
        struct_instance = {}
        for field_name, field_type in struct_fields.items():
            struct_instance[field_name] = self.get_default_value(field_type)
        return Value(struct_name, struct_instance)

    def get_default_value(self, var_type):
        if var_type == Type.INT:
            return Value(Type.INT, 0)
        elif var_type == Type.BOOL:
            return Value(Type.BOOL, False)
        elif var_type == Type.STRING:
            return Value(Type.STRING, "")
        elif var_type in self.structs:
            return Value(Type.NIL, None)
        else:
            super().error(ErrorType.TYPE_ERROR,
            f"Invalid type: {var_type}")

    def __eval_op(self, arith_ast):
        left_value_obj = self.__eval_expr(arith_ast.get("op1"))
        right_value_obj = self.__eval_expr(arith_ast.get("op2"))

        # probably add coercion of ints to bools and bools to ints somewhere here
        if not self.__compatible_types(
            arith_ast.elem_type, left_value_obj, right_value_obj
        ):
            if left_value_obj.type() == Type.BOOL and right_value_obj.type() == Type.INT():
                right_value_obj = self.__coerce_value(left_value_obj.type(), right_value_obj)
            elif left_value_obj.type() == Type.INT and right_value_obj.type() == Type.BOOL():
                left_value_obj = self.__coerce_value(right_value_obj.type(), left_value_obj)
            else:
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

    def __compatible_types(self, oper, obj1, obj2):
        # DOCUMENT: allow comparisons ==/!= of anything against anything
        if oper in ["==", "!="]:
            return True
        return obj1.type() == obj2.type()

    def __eval_unary(self, arith_ast, t, f):
        value_obj = self.__eval_expr(arith_ast.get("op1"))
        if value_obj.type() != t:
            # value_obj = self.__coerce_value(t, value_obj)
            # if value_obj.type() != Type.BOOL:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible type for {arith_ast.elem_type} operation",
            )
        return Value(t, f(value_obj.value()))

    def __setup_ops(self):
        self.op_to_lambda = {}
        # set up operations on integers
        self.op_to_lambda[Type.INT] = {}
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
        self.op_to_lambda[Type.INT]["=="] = lambda x, y: Value(
            Type.BOOL, x.type() == y.type() and x.value() == y.value()
        )
        self.op_to_lambda[Type.INT]["!="] = lambda x, y: Value(
            Type.BOOL, x.type() != y.type() or x.value() != y.value()
        )
        self.op_to_lambda[Type.INT]["<"] = lambda x, y: Value(
            Type.BOOL, x.value() < y.value()
        )
        self.op_to_lambda[Type.INT]["<="] = lambda x, y: Value(
            Type.BOOL, x.value() <= y.value()
        )
        self.op_to_lambda[Type.INT][">"] = lambda x, y: Value(
            Type.BOOL, x.value() > y.value()
        )
        self.op_to_lambda[Type.INT][">="] = lambda x, y: Value(
            Type.BOOL, x.value() >= y.value()
        )
        #  set up operations on strings
        self.op_to_lambda[Type.STRING] = {}
        self.op_to_lambda[Type.STRING]["+"] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.STRING]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.STRING]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        #  set up operations on bools
        self.op_to_lambda[Type.BOOL] = {}
        self.op_to_lambda[Type.BOOL]["&&"] = lambda x, y: Value(
            x.type(), x.value() and y.value()
        )
        self.op_to_lambda[Type.BOOL]["||"] = lambda x, y: Value(
            x.type(), x.value() or y.value()
        )
        self.op_to_lambda[Type.BOOL]["=="] = lambda x, y: Value(
            Type.BOOL, x.type() == y.type() and x.value() == y.value()
        )
        self.op_to_lambda[Type.BOOL]["!="] = lambda x, y: Value(
            Type.BOOL, x.type() != y.type() or x.value() != y.value()
        )

        #  set up operations on nil
        self.op_to_lambda[Type.NIL] = {}
        self.op_to_lambda[Type.NIL]["=="] = lambda x, y: Value(
            Type.BOOL, x.type() == y.type() and x.value() == y.value()
        )
        self.op_to_lambda[Type.NIL]["!="] = lambda x, y: Value(
            Type.BOOL, x.type() != y.type() or x.value() != y.value()
        )

    def __do_if(self, if_ast):
        cond_ast = if_ast.get("condition")
        result = self.__eval_expr(cond_ast)
        if result.type() != Type.BOOL:
            result = self.__coerce_value(Type.BOOL, result)
            # this should already have thrown an error if it couldn't coerce
        if result.value():
            statements = if_ast.get("statements")
            status, return_val = self.__run_statements(statements)
            return (status, return_val)
        else:
            else_statements = if_ast.get("else_statements")
            if else_statements is not None:
                status, return_val = self.__run_statements(else_statements)
                return (status, return_val)

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_for(self, for_ast):
        init_ast = for_ast.get("init") 
        cond_ast = for_ast.get("condition")
        update_ast = for_ast.get("update") 

        self.__run_statement(init_ast)  # initialize counter variable
        run_for = Interpreter.TRUE_VALUE
        while run_for.value():
            run_for = self.__eval_expr(cond_ast)  # check for-loop condition
            if run_for.type() != Type.BOOL:
                run_for = self.__coerce_value(Type.BOOL, run_for)
                # this should throw an error if it can't coerce
            if run_for.value():
                statements = for_ast.get("statements")
                status, return_val = self.__run_statements(statements)
                if status == ExecStatus.RETURN:
                    return status, return_val
                self.__run_statement(update_ast)  # update counter variable

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_return(self, return_ast):
        expr_ast = return_ast.get("expression")
        if expr_ast is None:
            return (ExecStatus.RETURN, Interpreter.NIL_VALUE)
        value = self.__eval_expr(expr_ast)
        if value.type() not in self.structs:
            if value.type() not in self.PRIMITIVES:
                super().error(
                    ErrorType.TYPE_ERROR,
                    f"Invalid Type returned {value.type()}"
                )
            value_obj = copy.copy(self.__eval_expr(expr_ast))
        return (ExecStatus.RETURN, value_obj)