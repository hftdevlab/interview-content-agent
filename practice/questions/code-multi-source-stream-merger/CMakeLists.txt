add_library(stream_merger_starter STATIC
    starter/stream_merger.cpp
)
target_include_directories(stream_merger_starter PUBLIC starter)

add_library(stream_merger_solution STATIC
    solution/stream_merger.cpp
)
target_include_directories(stream_merger_solution PUBLIC solution)

foreach(target stream_merger_starter stream_merger_solution)
    practice_configure_target(${target})
endforeach()

add_executable(stream_merger_test
    tests/stream_merger_test.cpp
)
target_link_libraries(stream_merger_test PRIVATE stream_merger_solution)
practice_configure_target(stream_merger_test)

add_executable(stream_merger_starter_test
    tests/stream_merger_test.cpp
)
target_link_libraries(stream_merger_starter_test PRIVATE stream_merger_starter)
practice_configure_target(stream_merger_starter_test)

add_test(NAME stream_merger_test COMMAND stream_merger_test)
set_tests_properties(stream_merger_test PROPERTIES LABELS "solution")

add_test(NAME stream_merger_starter_rejected COMMAND stream_merger_starter_test)
set_tests_properties(
    stream_merger_starter_rejected
    PROPERTIES
        WILL_FAIL TRUE
        LABELS "starter-negative"
)
