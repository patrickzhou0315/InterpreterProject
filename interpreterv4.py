# document that we won't have a return inside the init/update of a for loop

import copy
from enum import Enum

from brewparse import parse_program
from env_v4 import EnvironmentManager
from intbase import InterpreterBase, ErrorType
from type_valuev4 import Type, Value, create_value, get_printable
from lazy_valv4 import LazyVal

class ExecStatus(Enum):
    CONTINUE = 1
    RETURN = 2
    EXCEPTION = 3


# Main interpreter class
class Interpreter(InterpreterBase):
    # constants
    NIL_VALUE = create_value(InterpreterBase.NIL_DEF)
    TRUE_VALUE = create_value(InterpreterBase.TRUE_DEF)
    BIN_OPS = {"+", "-", "*", "/", "==", "!=", ">", ">=", "<", "<=", "||", "&&"}

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
        self.env = EnvironmentManager()
        exception_status, exception_value = self.__call_func_aux("main", [])
        if (exception_status == ExecStatus.EXCEPTION):
            super().error(
                ErrorType.FAULT_ERROR,
                f"Exception {exception_value.value()} thrown but not handled",
            )

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
            # if the status is either RETURN or EXCEPTION, then we return that
            if status == ExecStatus.RETURN or status == ExecStatus.EXCEPTION:
                self.env.pop_block()
                return (status, return_val)

        self.env.pop_block()
        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __run_statement(self, statement):
        status = ExecStatus.CONTINUE
        return_val = None

        # print statements are eagerly evaluated

        if statement.elem_type == InterpreterBase.FCALL_NODE:
            status, return_val = self.__call_func(statement)
        elif statement.elem_type == "=":
            status, return_val = self.__assign(statement)
        elif statement.elem_type == InterpreterBase.VAR_DEF_NODE:
            self.__var_def(statement)
        elif statement.elem_type == InterpreterBase.RETURN_NODE:
            status, return_val = self.__do_return(statement)

        # these are eagerly evaluated
        elif statement.elem_type == Interpreter.IF_NODE:
            status, return_val = self.__do_if(statement)
        elif statement.elem_type == Interpreter.FOR_NODE:
            status, return_val = self.__do_for(statement)
        elif statement.elem_type == Interpreter.RAISE_NODE:
            status, return_val = self.__do_raise(statement)


        elif statement.elem_type == Interpreter.TRY_NODE:
            status, return_val = self.__try_block(statement)
        return (status, return_val)
    
    def __try_block(self, try_node):
        # going through a try block
        status, return_val = self.__run_statements(try_node.get("statements"))
        # if the status is exception, look through current list of catchers
        if status == ExecStatus.EXCEPTION:
            for catcher in try_node.get("catchers"):
                # if the string value of the exception is the same as one of the catchers, do it
                if return_val.value() == catcher.get("exception_type"):
                    status, return_val = self.__run_statements(catcher.get("statements"))
                    return (status,return_val)
            # if all the catchers have been gone through, but it still hasn't been found, just propagate the exception upward by returning
            return (status, return_val)
        # if the status is not an exception, just return that status instead, it is either a continue or a return
        else:
            return (status, return_val)
    
# EAGER EVALUATION HERE
    def __do_raise(self, raise_ast):
        expr_ast = raise_ast.get("exception_type")

        # if the exception raised has no string in it, then we return an exception type with a nil value
        if expr_ast is None:
            return (ExecStatus.EXCEPTION, Interpreter.NIL_VALUE)
        # otherwise we evaluate the expression
        _, value_obj = copy.copy(self.__eval_expr(expr_ast))
        # make sure that it's a string for the evaluation
        if value_obj.type() != Type.STRING:
            super().error(
                ErrorType.TYPE_ERROR,
                "incompatible type for raise statement",
            )

        # return that we've hit an exception
        return (ExecStatus.EXCEPTION, value_obj)
    
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
            exception_status, result = copy.copy(self.__eval_expr(actual_ast))
            if (exception_status == ExecStatus.EXCEPTION):
                return (exception_status, result)
            arg_name = formal_ast.get("name")
            args[arg_name] = result

        # then create the new activation record 
        self.env.push_func()
        # and add the formal arguments to the activation record
        for arg_name, value in args.items():
          self.env.create(arg_name, value)

        # the return value of the function
        # now can either continue to return an exception or actually return a value
        exception_status, return_val = self.__run_statements(func_ast.get("statements"))
        # if an exception wasn't handled inside the thing and it propagated upwards, we return the exception to be handled
        self.env.pop_func()
        return (exception_status, return_val)


# EAGER EVALUATION HERE
    def __call_print(self, args):
        output = ""
        for arg in args:
            exception_status, result = self.__eval_expr(arg)  # result is a Value object
            if (exception_status == ExecStatus.EXCEPTION):
                return (ExecStatus.EXCEPTION, result)
            output = output + get_printable(result)
        super().output(output)
        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __call_input(self, name, args):
        if args is not None and len(args) == 1:
            exception_status, result = self.__eval_expr(args[0])
            if (exception_status == ExecStatus.EXCEPTION):
                return (ExecStatus.EXCEPTION, result)
            super().output(get_printable(result))
        elif args is not None and len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter"
            )
        inp = super().get_input()
        if name == "inputi":
            return (ExecStatus.CONTINUE, Value(Type.INT, int(inp)))
        if name == "inputs":
            return (ExecStatus.CONTINUE, Value(Type.STRING, inp))

    def __assign(self, assign_ast):
        var_name = assign_ast.get("name")
        exception_status, value_obj = self.__eval_expr(assign_ast.get("expression"))
        if (exception_status == ExecStatus.EXCEPTION):
            return (ExecStatus.EXCEPTION, value_obj)
        if not self.env.set(var_name, value_obj):
            super().error(
                ErrorType.NAME_ERROR, f"Undefined variable {var_name} in assignment"
            )
        return (ExecStatus.CONTINUE, Value(Type.BOOL, True))
    
    def __var_def(self, var_ast):
        var_name = var_ast.get("name")
        if not self.env.create(var_name, Interpreter.NIL_VALUE):
            super().error(
                ErrorType.NAME_ERROR, f"Duplicate definition for variable {var_name}"
            )

    def __eval_expr(self, expr_ast):
        if expr_ast.elem_type == InterpreterBase.NIL_NODE:
            return ExecStatus.CONTINUE, Interpreter.NIL_VALUE
        if expr_ast.elem_type == InterpreterBase.INT_NODE:
            return ExecStatus.CONTINUE, Value(Type.INT, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.STRING_NODE:
            return ExecStatus.CONTINUE, Value(Type.STRING, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.BOOL_NODE:
            return ExecStatus.CONTINUE, Value(Type.BOOL, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.VAR_NODE:
            var_name = expr_ast.get("name")
            val = self.env.get(var_name)
            if val is None:
                super().error(ErrorType.NAME_ERROR, f"Variable {var_name} not found")
            return ExecStatus.CONTINUE, val
        if expr_ast.elem_type == InterpreterBase.FCALL_NODE:
            exception_status, return_val = self.__call_func(expr_ast)
            return exception_status, return_val
        if expr_ast.elem_type in Interpreter.BIN_OPS:
            return self.__eval_op(expr_ast)
        if expr_ast.elem_type == Interpreter.NEG_NODE:
            return self.__eval_unary(expr_ast, Type.INT, lambda x: -1 * x)
        if expr_ast.elem_type == Interpreter.NOT_NODE:
            return self.__eval_unary(expr_ast, Type.BOOL, lambda x: not x)

    def __eval_op(self, arith_ast):
        left_exception_status, left_value_obj = self.__eval_expr(arith_ast.get("op1"))
        # check the exception statsus
        if (left_exception_status == ExecStatus.EXCEPTION):
            return (ExecStatus.EXCEPTION, left_value_obj)


        # Short Circuiting

        # checking the expression type

        # if it's &&, check if left value is False, just return False
        if (arith_ast.elem_type == "&&"):
            if (left_value_obj.type() != Type.BOOL):
                super().error(
                    ErrorType.TYPE_ERROR,
                    f"Incompatible left type for {arith_ast.elem_type} operation",
                )
            if left_value_obj.value() == False:
                return ExecStatus.CONTINUE, Value(Type.BOOL, False)

        # if it's ||, check if left value is True, just return True
        if (arith_ast.elem_type == "||"):
            if (left_value_obj.type() != Type.BOOL):
                super().error(
                    ErrorType.TYPE_ERROR,
                    f"Incompatible left type for {arith_ast.elem_type} operation",
                )
            if left_value_obj.value() == True:
                return ExecStatus.CONTINUE, Value(Type.BOOL, True)

        # if none of the short circuits worked, evaluate the right value object
        right_exception_status, right_value_obj = self.__eval_expr(arith_ast.get("op2"))

        # check exception status
        if (right_exception_status == ExecStatus.EXCEPTION):
            return (ExecStatus.EXCEPTION, right_value_obj)

        if not self.__compatible_types(
            arith_ast.elem_type, left_value_obj, right_value_obj
        ):
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
        if (arith_ast.elem_type == "/" and right_value_obj.type() == Type.INT and right_value_obj.value() == 0):
            return ExecStatus.EXCEPTION, Value(Type.STRING, "div0")
        return ExecStatus.CONTINUE, f(left_value_obj, right_value_obj)

    def __compatible_types(self, oper, obj1, obj2):
        # DOCUMENT: allow comparisons ==/!= of anything against anything
        if oper in ["==", "!="]:
            return True
        return obj1.type() == obj2.type()

    def __eval_unary(self, arith_ast, t, f):
        exception_status, value_obj = self.__eval_expr(arith_ast.get("op1"))
        if (exception_status == ExecStatus.EXCEPTION):
            return (ExecStatus.EXCEPTION, value_obj)

        if value_obj.type() != t:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible type for {arith_ast.elem_type} operation",
            )
        return ExecStatus.CONTINUE, Value(t, f(value_obj.value()))

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

# EAGER EVALUATION HERE FOR CONDITION
    def __do_if(self, if_ast):
        cond_ast = if_ast.get("condition")
        exception_status, result = self.__eval_expr(cond_ast)
        if exception_status == ExecStatus.EXCEPTION:
            return (ExecStatus.EXCEPTION, result)
        if result.type() != Type.BOOL:
            super().error(
                ErrorType.TYPE_ERROR,
                "Incompatible type for if condition",
            )
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

# EAGER EVALUATION HERE FOR CONDITION
    def __do_for(self, for_ast):
        init_ast = for_ast.get("init") 
        cond_ast = for_ast.get("condition")
        update_ast = for_ast.get("update") 

        exception_status, return_value = self.__run_statement(init_ast)  # initialize counter variable
        if (exception_status == ExecStatus.EXCEPTION):
            return (ExecStatus.EXCEPTION, return_value)
        run_for = Interpreter.TRUE_VALUE
        while run_for.value():
            exception_status, run_for = self.__eval_expr(cond_ast)  # check for-loop condition
            if (exception_status == ExecStatus.EXCEPTION):
                return (ExecStatus.EXCEPTION, run_for)
            if run_for.type() != Type.BOOL:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible type for for condition",
                )
            if run_for.value():
                statements = for_ast.get("statements")
                status, return_val = self.__run_statements(statements)
                if status == ExecStatus.EXCEPTION:
                    return status, return_val
                if status == ExecStatus.RETURN:
                    return status, return_val
                status, return_val = self.__run_statement(update_ast)  # update counter variable
                if status == ExecStatus.EXCEPTION:
                    return status, return_val

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_return(self, return_ast):
        expr_ast = return_ast.get("expression")
        if expr_ast is None:
            return (ExecStatus.RETURN, Interpreter.NIL_VALUE)
        exception_status, returned_value = self.__eval_expr(expr_ast)
        if (exception_status == ExecStatus.EXCEPTION):
            return (ExecStatus.EXCEPTION, returned_value)
        value_obj = copy.copy(returned_value)
        return (ExecStatus.RETURN, value_obj)