import os
import time
import unittest

from httprunner import testcase
from httprunner.exception import (ApiNotFound, FileFormatError,
                                  FileNotFoundError, ParamsError,
                                  SuiteNotFound)
from httprunner.testcase import TestcaseLoader


class TestTestcaseLoader(unittest.TestCase):

    def setUp(self):
        TestcaseLoader.overall_def_dict = {
            "api": {},
            "suite": {}
        }

    def test_load_test_dependencies(self):
        TestcaseLoader.load_test_dependencies()
        overall_def_dict = TestcaseLoader.overall_def_dict
        self.assertIn("get_token", overall_def_dict["api"])
        self.assertIn("create_and_check", overall_def_dict["suite"])

    def test_load_api_file(self):
        TestcaseLoader.load_api_file("tests/api/basic.yml")
        overall_api_def_dict = TestcaseLoader.overall_def_dict["api"]
        self.assertIn("get_token",overall_api_def_dict)
        self.assertEqual("/api/get-token", overall_api_def_dict["get_token"]["request"]["url"])
        self.assertIn("$user_agent", overall_api_def_dict["get_token"]["function_meta"]["args"])
        self.assertEqual(len(overall_api_def_dict["get_token"]["validate"]), 3)

    def test_load_test_file_suite(self):
        TestcaseLoader.load_api_file("tests/api/basic.yml")
        testset = TestcaseLoader.load_test_file("tests/suite/create_and_get.yml")
        self.assertEqual(testset["name"], "create user and check result.")
        self.assertEqual(testset["config"]["name"], "create user and check result.")
        self.assertEqual(len(testset["testcases"]), 3)
        self.assertEqual(testset["testcases"][0]["name"], "make sure user $uid does not exist")
        self.assertEqual(testset["testcases"][0]["request"]["url"], "/api/users/$uid")

    def test_load_test_file_testcase(self):
        TestcaseLoader.load_test_dependencies()
        testset = TestcaseLoader.load_test_file("tests/testcases/smoketest.yml")
        self.assertEqual(testset["name"], "smoketest")
        self.assertEqual(testset["config"]["path"], "tests/testcases/smoketest.yml")
        self.assertIn("device_sn", testset["config"]["variables"][0])
        self.assertEqual(len(testset["testcases"]), 8)
        self.assertEqual(testset["testcases"][0]["name"], "get token")

    def test_get_block_by_name(self):
        TestcaseLoader.load_test_dependencies()
        ref_call = "get_user($uid, $token)"
        block = TestcaseLoader._get_block_by_name(ref_call, "api")
        self.assertEqual(block["request"]["url"], "/api/users/$uid")
        self.assertEqual(block["function_meta"]["func_name"], "get_user")
        self.assertEqual(block["function_meta"]["args"], ['$uid', '$token'])

    def test_get_block_by_name_args_mismatch(self):
        TestcaseLoader.load_test_dependencies()
        ref_call = "get_user($uid, $token, $var)"
        with self.assertRaises(ParamsError):
            TestcaseLoader._get_block_by_name(ref_call, "api")

    def test_get_test_definition_api(self):
        TestcaseLoader.load_test_dependencies()
        api_def = TestcaseLoader._get_test_definition("get_token", "api")
        self.assertEqual(api_def["request"]["url"], "/api/get-token")

        with self.assertRaises(ApiNotFound):
            TestcaseLoader._get_test_definition("get_token_XXX", "api")

    def test_get_test_definition_suite(self):
        TestcaseLoader.load_test_dependencies()
        api_def = TestcaseLoader._get_test_definition("create_and_check", "suite")
        self.assertEqual(api_def["name"], "create user and check result.")

        with self.assertRaises(SuiteNotFound):
            TestcaseLoader._get_test_definition("create_and_check_XXX", "suite")

    def test_override_block(self):
        TestcaseLoader.load_test_dependencies()
        def_block = TestcaseLoader._get_block_by_name("get_token($user_agent, $device_sn, $os_platform, $app_version)", "api")
        test_block = {
            "name": "override block",
            "variables": [
                {"var": 123}
            ],
            'request': {
                'url': '/api/get-token', 'method': 'POST', 'headers': {'user_agent': '$user_agent', 'device_sn': '$device_sn', 'os_platform': '$os_platform', 'app_version': '$app_version'}, 'json': {'sign': '${get_sign($user_agent, $device_sn, $os_platform, $app_version)}'}},
            'validate': [
                {'eq': ['status_code', 201]},
                {'len_eq': ['content.token', 32]}
            ]
        }

        TestcaseLoader._override_block(def_block, test_block)
        self.assertEqual(test_block["name"], "override block")
        self.assertIn({'check': 'status_code', 'expect': 201, 'comparator': 'eq'}, test_block["validate"])
        self.assertIn({'check': 'content.token', 'comparator': 'len_eq', 'expect': 32}, test_block["validate"])

    def test_load_testcases_by_path_files(self):
        testsets_list = []

        # absolute file path
        path = os.path.join(
            os.getcwd(), 'tests/data/demo_testset_hardcode.json')
        testset_list = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(len(testset_list), 1)
        self.assertIn("path", testset_list[0]["config"])
        self.assertEqual(testset_list[0]["config"]["path"], path)
        self.assertEqual(len(testset_list[0]["testcases"]), 3)
        testsets_list.extend(testset_list)

        # relative file path
        path = 'tests/data/demo_testset_hardcode.yml'
        testset_list = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(len(testset_list), 1)
        self.assertIn("path", testset_list[0]["config"])
        self.assertIn(path, testset_list[0]["config"]["path"])
        self.assertEqual(len(testset_list[0]["testcases"]), 3)
        testsets_list.extend(testset_list)

        # list/set container with file(s)
        path = [
            os.path.join(os.getcwd(), 'tests/data/demo_testset_hardcode.json'),
            'tests/data/demo_testset_hardcode.yml'
        ]
        testset_list = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(len(testset_list), 2)
        self.assertEqual(len(testset_list[0]["testcases"]), 3)
        self.assertEqual(len(testset_list[1]["testcases"]), 3)
        testsets_list.extend(testset_list)
        self.assertEqual(len(testsets_list), 4)

        for testset in testsets_list:
            for test in testset["testcases"]:
                self.assertIn('name', test)
                self.assertIn('request', test)
                self.assertIn('url', test['request'])
                self.assertIn('method', test['request'])

    def test_load_testcases_by_path_folder(self):
        TestcaseLoader.load_test_dependencies()
        # absolute folder path
        path = os.path.join(os.getcwd(), 'tests/data')
        testset_list_1 = TestcaseLoader.load_testsets_by_path(path)
        self.assertGreater(len(testset_list_1), 4)

        # relative folder path
        path = 'tests/data/'
        testset_list_2 = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(len(testset_list_1), len(testset_list_2))

        # list/set container with file(s)
        path = [
            os.path.join(os.getcwd(), 'tests/data'),
            'tests/data/'
        ]
        testset_list_3 = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(len(testset_list_3), 2 * len(testset_list_1))

    def test_load_testcases_by_path_not_exist(self):
        # absolute folder path
        path = os.path.join(os.getcwd(), 'tests/data_not_exist')
        testset_list_1 = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(testset_list_1, [])

        # relative folder path
        path = 'tests/data_not_exist'
        testset_list_2 = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(testset_list_2, [])

        # list/set container with file(s)
        path = [
            os.path.join(os.getcwd(), 'tests/data_not_exist'),
            'tests/data_not_exist/'
        ]
        testset_list_3 = TestcaseLoader.load_testsets_by_path(path)
        self.assertEqual(testset_list_3, [])

    def test_load_testcases_by_path_layered(self):
        TestcaseLoader.load_test_dependencies()
        path = os.path.join(
            os.getcwd(), 'tests/data/demo_testset_layer.yml')
        testsets_list = TestcaseLoader.load_testsets_by_path(path)
        self.assertIn("variables", testsets_list[0]["config"])
        self.assertIn("request", testsets_list[0]["config"])
        self.assertIn("request", testsets_list[0]["testcases"][0])
        self.assertIn("url", testsets_list[0]["testcases"][0]["request"])
        self.assertIn("validate", testsets_list[0]["testcases"][0])


class TestcaseParserUnittest(unittest.TestCase):

    def test_cartesian_product_one(self):
        parameters_content_list = [
            [
                {"a": 1},
                {"a": 2}
            ]
        ]
        product_list = testcase.gen_cartesian_product(*parameters_content_list)
        self.assertEqual(
            product_list,
            [
                {"a": 1},
                {"a": 2}
            ]
        )

    def test_cartesian_product_multiple(self):
        parameters_content_list = [
            [
                {"a": 1},
                {"a": 2}
            ],
            [
                {"x": 111, "y": 112},
                {"x": 121, "y": 122}
            ]
        ]
        product_list = testcase.gen_cartesian_product(*parameters_content_list)
        self.assertEqual(
            product_list,
            [
                {'a': 1, 'x': 111, 'y': 112},
                {'a': 1, 'x': 121, 'y': 122},
                {'a': 2, 'x': 111, 'y': 112},
                {'a': 2, 'x': 121, 'y': 122}
            ]
        )

    def test_cartesian_product_empty(self):
        parameters_content_list = []
        product_list = testcase.gen_cartesian_product(*parameters_content_list)
        self.assertEqual(product_list, [])

    def test_parse_parameters_raw_list(self):
        parameters = [
            {"user_agent": ["iOS/10.1", "iOS/10.2", "iOS/10.3"]},
            {"username-password": [("user1", "111111"), ["test2", "222222"]]}
        ]
        cartesian_product_parameters = testcase.parse_parameters(parameters)
        self.assertEqual(
            len(cartesian_product_parameters),
            3 * 2
        )
        self.assertEqual(
            cartesian_product_parameters[0],
            {'user_agent': 'iOS/10.1', 'username': 'user1', 'password': '111111'}
        )

    def test_parse_parameters_parameterize(self):
        parameters = [
            {"app_version": "${parameterize(app_version.csv)}"},
            {"username-password": "${parameterize(account.csv)}"}
        ]
        testset_path = os.path.join(
            os.getcwd(),
            "tests/data/demo_parameters.yml"
        )
        cartesian_product_parameters = testcase.parse_parameters(
            parameters,
            testset_path
        )
        self.assertEqual(
            len(cartesian_product_parameters),
            2 * 3
        )

    def test_parse_parameters_custom_function(self):
        parameters = [
            {"app_version": "${gen_app_version()}"},
            {"username-password": "${get_account()}"}
        ]
        testset_path = os.path.join(
            os.getcwd(),
            "tests/data/demo_parameters.yml"
        )
        cartesian_product_parameters = testcase.parse_parameters(
            parameters,
            testset_path
        )
        self.assertEqual(
            len(cartesian_product_parameters),
            2 * 2
        )

    def test_parse_parameters_mix(self):
        parameters = [
            {"user_agent": ["iOS/10.1", "iOS/10.2", "iOS/10.3"]},
            {"app_version": "${gen_app_version()}"},
            {"username-password": "${parameterize(account.csv)}"}
        ]
        testset_path = os.path.join(
            os.getcwd(),
            "tests/data/demo_parameters.yml"
        )
        cartesian_product_parameters = testcase.parse_parameters(
            parameters,
            testset_path
        )
        self.assertEqual(
            len(cartesian_product_parameters),
            3 * 2 * 3
        )

    def test_extract_variables(self):
        self.assertEqual(
            testcase.extract_variables("$var"),
            ["var"]
        )
        self.assertEqual(
            testcase.extract_variables("$var123"),
            ["var123"]
        )
        self.assertEqual(
            testcase.extract_variables("$var_name"),
            ["var_name"]
        )
        self.assertEqual(
            testcase.extract_variables("var"),
            []
        )
        self.assertEqual(
            testcase.extract_variables("a$var"),
            ["var"]
        )
        self.assertEqual(
            testcase.extract_variables("$v ar"),
            ["v"]
        )
        self.assertEqual(
            testcase.extract_variables(" "),
            []
        )
        self.assertEqual(
            testcase.extract_variables("$abc*"),
            ["abc"]
        )
        self.assertEqual(
            testcase.extract_variables("${func()}"),
            []
        )
        self.assertEqual(
            testcase.extract_variables("${func(1,2)}"),
            []
        )
        self.assertEqual(
            testcase.extract_variables("${gen_md5($TOKEN, $data, $random)}"),
            ["TOKEN", "data", "random"]
        )

    def test_eval_content_variables(self):
        variables = {
            "var_1": "abc",
            "var_2": "def",
            "var_3": 123,
            "var_4": {"a": 1},
            "var_5": True,
            "var_6": None
        }
        testcase_parser = testcase.TestcaseParser(variables=variables)
        self.assertEqual(
            testcase_parser._eval_content_variables("$var_1"),
            "abc"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("var_1"),
            "var_1"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("$var_1#XYZ"),
            "abc#XYZ"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("/$var_1/$var_2/var3"),
            "/abc/def/var3"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("/$var_1/$var_2/$var_1"),
            "/abc/def/abc"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("${func($var_1, $var_2, xyz)}"),
            "${func(abc, def, xyz)}"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("$var_3"),
            123
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("$var_4"),
            {"a": 1}
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("$var_5"),
            True
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("abc$var_5"),
            "abcTrue"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("abc$var_4"),
            "abc{'a': 1}"
        )
        self.assertEqual(
            testcase_parser._eval_content_variables("$var_6"),
            None
        )

    def test_eval_content_variables_search_upward(self):
        testcase_parser = testcase.TestcaseParser()

        with self.assertRaises(ParamsError):
            testcase_parser._eval_content_variables("/api/$SECRET_KEY")

        testcase_parser.file_path = "tests/data/demo_testset_hardcode.yml"
        content = testcase_parser._eval_content_variables("/api/$SECRET_KEY")
        self.assertEqual(content, "/api/DebugTalk")

    def test_parse_string_value(self):
        self.assertEqual(testcase.parse_string_value("123"), 123)
        self.assertEqual(testcase.parse_string_value("12.3"), 12.3)
        self.assertEqual(testcase.parse_string_value("a123"), "a123")
        self.assertEqual(testcase.parse_string_value("$var"), "$var")
        self.assertEqual(testcase.parse_string_value("${func}"), "${func}")

    def test_parse_function(self):
        self.assertEqual(
            testcase.parse_function("func()"),
            {'func_name': 'func', 'args': [], 'kwargs': {}}
        )
        self.assertEqual(
            testcase.parse_function("func(5)"),
            {'func_name': 'func', 'args': [5], 'kwargs': {}}
        )
        self.assertEqual(
            testcase.parse_function("func(1, 2)"),
            {'func_name': 'func', 'args': [1, 2], 'kwargs': {}}
        )
        self.assertEqual(
            testcase.parse_function("func(a=1, b=2)"),
            {'func_name': 'func', 'args': [], 'kwargs': {'a': 1, 'b': 2}}
        )
        self.assertEqual(
            testcase.parse_function("func(a= 1, b =2)"),
            {'func_name': 'func', 'args': [], 'kwargs': {'a': 1, 'b': 2}}
        )
        self.assertEqual(
            testcase.parse_function("func(1, 2, a=3, b=4)"),
            {'func_name': 'func', 'args': [1, 2], 'kwargs': {'a': 3, 'b': 4}}
        )
        self.assertEqual(
            testcase.parse_function("func($request, 123)"),
            {'func_name': 'func', 'args': ["$request", 123], 'kwargs': {}}
        )
        self.assertEqual(
            testcase.parse_function("func( )"),
            {'func_name': 'func', 'args': [], 'kwargs': {}}
        )
        self.assertEqual(
            testcase.parse_function("func(hello world, a=3, b=4)"),
            {'func_name': 'func', 'args': ["hello world"], 'kwargs': {'a': 3, 'b': 4}}
        )
        self.assertEqual(
            testcase.parse_function("func($request, 12 3)"),
            {'func_name': 'func', 'args': ["$request", '12 3'], 'kwargs': {}}
        )


    def test_parse_content_with_bindings_variables(self):
        variables = {
            "str_1": "str_value1",
            "str_2": "str_value2"
        }
        testcase_parser = testcase.TestcaseParser(variables=variables)
        self.assertEqual(
            testcase_parser.eval_content_with_bindings("$str_1"),
            "str_value1"
        )
        self.assertEqual(
            testcase_parser.eval_content_with_bindings("123$str_1/456"),
            "123str_value1/456"
        )

        with self.assertRaises(ParamsError):
            testcase_parser.eval_content_with_bindings("$str_3")

        self.assertEqual(
            testcase_parser.eval_content_with_bindings(["$str_1", "str3"]),
            ["str_value1", "str3"]
        )
        self.assertEqual(
            testcase_parser.eval_content_with_bindings({"key": "$str_1"}),
            {"key": "str_value1"}
        )

    def test_parse_content_with_bindings_multiple_identical_variables(self):
        variables = {
            "userid": 100,
            "data": 1498
        }
        testcase_parser = testcase.TestcaseParser(variables=variables)
        content = "/users/$userid/training/$data?userId=$userid&data=$data"
        self.assertEqual(
            testcase_parser.eval_content_with_bindings(content),
            "/users/100/training/1498?userId=100&data=1498"
        )

    def test_parse_variables_multiple_identical_variables(self):
        variables = {
            "user": 100,
            "userid": 1000,
            "data": 1498
        }
        testcase_parser = testcase.TestcaseParser(variables=variables)
        content = "/users/$user/$userid/$data?userId=$userid&data=$data"
        self.assertEqual(
            testcase_parser.eval_content_with_bindings(content),
            "/users/100/1000/1498?userId=1000&data=1498"
        )

    def test_parse_content_with_bindings_functions(self):
        import random, string
        functions = {
            "gen_random_string": lambda str_len: ''.join(random.choice(string.ascii_letters + string.digits) \
                for _ in range(str_len))
        }
        testcase_parser = testcase.TestcaseParser(functions=functions)

        result = testcase_parser.eval_content_with_bindings("${gen_random_string(5)}")
        self.assertEqual(len(result), 5)

        add_two_nums = lambda a, b=1: a + b
        functions["add_two_nums"] = add_two_nums
        self.assertEqual(
            testcase_parser.eval_content_with_bindings("${add_two_nums(1)}"),
            2
        )
        self.assertEqual(
            testcase_parser.eval_content_with_bindings("${add_two_nums(1, 2)}"),
            3
        )

    def test_extract_functions(self):
        self.assertEqual(
            testcase.extract_functions("${func()}"),
            ["func()"]
        )
        self.assertEqual(
            testcase.extract_functions("${func(5)}"),
            ["func(5)"]
        )
        self.assertEqual(
            testcase.extract_functions("${func(a=1, b=2)}"),
            ["func(a=1, b=2)"]
        )
        self.assertEqual(
            testcase.extract_functions("${func(1, $b, c=$x, d=4)}"),
            ["func(1, $b, c=$x, d=4)"]
        )
        self.assertEqual(
            testcase.extract_functions("/api/1000?_t=${get_timestamp()}"),
            ["get_timestamp()"]
        )
        self.assertEqual(
            testcase.extract_functions("/api/${add(1, 2)}"),
            ["add(1, 2)"]
        )
        self.assertEqual(
            testcase.extract_functions("/api/${add(1, 2)}?_t=${get_timestamp()}"),
            ["add(1, 2)", "get_timestamp()"]
        )
        self.assertEqual(
            testcase.extract_functions("abc${func(1, 2, a=3, b=4)}def"),
            ["func(1, 2, a=3, b=4)"]
        )

    def test_eval_content_functions(self):
        functions = {
            "add_two_nums": lambda a, b=1: a + b
        }
        testcase_parser = testcase.TestcaseParser(functions=functions)
        self.assertEqual(
            testcase_parser._eval_content_functions("${add_two_nums(1, 2)}"),
            3
        )
        self.assertEqual(
            testcase_parser._eval_content_functions("/api/${add_two_nums(1, 2)}"),
            "/api/3"
        )

    def test_eval_content_functions_search_upward(self):
        testcase_parser = testcase.TestcaseParser()

        with self.assertRaises(ParamsError):
            testcase_parser._eval_content_functions("/api/${gen_md5(abc)}")

        testcase_parser.file_path = "tests/data/demo_testset_hardcode.yml"
        content = testcase_parser._eval_content_functions("/api/${gen_md5(abc)}")
        self.assertEqual(content, "/api/900150983cd24fb0d6963f7d28e17f72")

    def test_parse_content_with_bindings_testcase(self):
        variables = {
            "uid": "1000",
            "random": "A2dEx",
            "authorization": "a83de0ff8d2e896dbd8efb81ba14e17d",
            "data": {"name": "user", "password": "123456"}
        }
        functions = {
            "add_two_nums": lambda a, b=1: a + b,
            "get_timestamp": lambda: int(time.time() * 1000)
        }
        testcase_template = {
            "url": "http://127.0.0.1:5000/api/users/$uid/${add_two_nums(1,2)}",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json",
                "authorization": "$authorization",
                "random": "$random",
                "sum": "${add_two_nums(1, 2)}"
            },
            "body": "$data"
        }
        parsed_testcase = testcase.TestcaseParser(variables, functions)\
            .eval_content_with_bindings(testcase_template)

        self.assertEqual(
            parsed_testcase["url"],
            "http://127.0.0.1:5000/api/users/1000/3"
        )
        self.assertEqual(
            parsed_testcase["headers"]["authorization"],
            variables["authorization"]
        )
        self.assertEqual(
            parsed_testcase["headers"]["random"],
            variables["random"]
        )
        self.assertEqual(
            parsed_testcase["body"],
            variables["data"]
        )
        self.assertEqual(
            parsed_testcase["headers"]["sum"],
            3
        )


    def test_substitute_variables_with_mapping(self):
        content = {
            'request': {
                'url': '/api/users/$uid',
                'method': "$method",
                'headers': {'token': '$token'},
                'data': {
                    "null": None,
                    "true": True,
                    "false": False,
                    "empty_str": ""
                }
            }
        }
        mapping = {
            "$uid": 1000,
            "$method": "POST"
        }
        result = testcase.substitute_variables_with_mapping(content, mapping)
        self.assertEqual("/api/users/1000", result["request"]["url"])
        self.assertEqual("$token", result["request"]["headers"]["token"])
        self.assertEqual("POST", result["request"]["method"])
        self.assertIsNone(result["request"]["data"]["null"])
        self.assertTrue(result["request"]["data"]["true"])
        self.assertFalse(result["request"]["data"]["false"])
        self.assertEqual("", result["request"]["data"]["empty_str"])


    def test_parse_validator(self):
        validator = {"check": "status_code", "comparator": "eq", "expect": 201}
        self.assertEqual(
            testcase.parse_validator(validator),
            {"check": "status_code", "comparator": "eq", "expect": 201}
        )

        validator = {'eq': ['status_code', 201]}
        self.assertEqual(
            testcase.parse_validator(validator),
            {"check": "status_code", "comparator": "eq", "expect": 201}
        )

    def test_merge_validator(self):
        def_validators = [
            {'eq': ['v1', 200]},
            {"check": "s2", "expect": 16, "comparator": "len_eq"}
        ]
        current_validators = [
            {"check": "v1", "expect": 201},
            {'len_eq': ['s3', 12]}
        ]

        merged_validators = testcase._merge_validator(def_validators, current_validators)
        self.assertIn(
            {"check": "v1", "expect": 201, "comparator": "eq"},
            merged_validators
        )
        self.assertIn(
            {"check": "s2", "expect": 16, "comparator": "len_eq"},
            merged_validators
        )
        self.assertIn(
            {"check": "s3", "expect": 12, "comparator": "len_eq"},
            merged_validators
        )

    def test_merge_validator_with_dict(self):
        def_validators = [
            {'eq': ["a", {"v": 1}]},
            {'eq': [{"b": 1}, 200]}
        ]
        current_validators = [
            {'len_eq': ['s3', 12]},
            {'eq': [{"b": 1}, 201]}
        ]

        merged_validators = testcase._merge_validator(def_validators, current_validators)
        self.assertEqual(len(merged_validators), 3)
        self.assertIn({'check': {'b': 1}, 'expect': 201, 'comparator': 'eq'}, merged_validators)
        self.assertNotIn({'check': {'b': 1}, 'expect': 200, 'comparator': 'eq'}, merged_validators)

    def test_merge_extractor(self):
        api_extrators = [{"var1": "val1"}, {"var2": "val2"}]
        current_extractors = [{"var1": "val111"}, {"var3": "val3"}]

        merged_extractors = testcase._merge_extractor(api_extrators, current_extractors)
        self.assertIn(
            {"var1": "val111"},
            merged_extractors
        )
        self.assertIn(
            {"var2": "val2"},
            merged_extractors
        )
        self.assertIn(
            {"var3": "val3"},
            merged_extractors
        )

    def test_is_testsets(self):
        data_structure = "path/to/file"
        self.assertFalse(testcase.is_testsets(data_structure))
        data_structure = ["path/to/file1", "path/to/file2"]
        self.assertFalse(testcase.is_testsets(data_structure))

        data_structure = {
            "name": "desc1",
            "config": {},
            "api": {},
            "testcases": ["testcase11", "testcase12"]
        }
        self.assertTrue(data_structure)
        data_structure = [
            {
                "name": "desc1",
                "config": {},
                "api": {},
                "testcases": ["testcase11", "testcase12"]
            },
            {
                "name": "desc2",
                "config": {},
                "api": {},
                "testcases": ["testcase21", "testcase22"]
            }
        ]
        self.assertTrue(data_structure)
