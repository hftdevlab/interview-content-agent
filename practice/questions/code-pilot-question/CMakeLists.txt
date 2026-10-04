add_library(simple_vector_starter STATIC
    starter/simple_vector.cpp
)
target_include_directories(simple_vector_starter PUBLIC starter)

add_library(simple_vector_solution STATIC
    solution/simple_vector.cpp
)
target_include_directories(simple_vector_solution PUBLIC solution)

foreach(target simple_vector_starter simple_vector_solution)
    practice_configure_target(${target})
endforeach()

add_executable(simple_vector_test
    tests/simple_vector_test.cpp
)
target_link_libraries(simple_vector_test PRIVATE simple_vector_solution)
practice_configure_target(simple_vector_test)

add_executable(simple_vector_starter_test
    tests/simple_vector_test.cpp
)
target_link_libraries(simple_vector_starter_test PRIVATE simple_vector_starter)
practice_configure_target(simple_vector_starter_test)

add_test(NAME simple_vector_test COMMAND simple_vector_test)
set_tests_properties(simple_vector_test PROPERTIES LABELS "solution")

add_test(NAME simple_vector_starter_rejected COMMAND simple_vector_starter_test)
set_tests_properties(
    simple_vector_starter_rejected
    PROPERTIES
        WILL_FAIL TRUE
        LABELS "starter-negative"
)
