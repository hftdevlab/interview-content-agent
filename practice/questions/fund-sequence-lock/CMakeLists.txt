add_library(sequence_snapshot_starter STATIC
    starter/quote_snapshot.cpp
)
target_include_directories(sequence_snapshot_starter PUBLIC starter)

add_library(sequence_snapshot_solution STATIC
    solution/quote_snapshot.cpp
)
target_include_directories(sequence_snapshot_solution PUBLIC solution)
target_link_libraries(sequence_snapshot_solution PUBLIC Threads::Threads)

foreach(target sequence_snapshot_starter sequence_snapshot_solution)
    practice_configure_target(${target})
endforeach()

add_executable(sequence_snapshot_test
    tests/quote_snapshot_test.cpp
)
target_link_libraries(sequence_snapshot_test PRIVATE sequence_snapshot_solution)
practice_configure_target(sequence_snapshot_test)

add_executable(sequence_snapshot_starter_test
    tests/quote_snapshot_test.cpp
)
target_link_libraries(
    sequence_snapshot_starter_test
    PRIVATE
        sequence_snapshot_starter
        Threads::Threads
)
practice_configure_target(sequence_snapshot_starter_test)

add_test(NAME sequence_snapshot_test COMMAND sequence_snapshot_test)
set_tests_properties(sequence_snapshot_test PROPERTIES LABELS "solution")

add_test(NAME sequence_snapshot_starter_rejected COMMAND sequence_snapshot_starter_test)
set_tests_properties(
    sequence_snapshot_starter_rejected
    PROPERTIES
        WILL_FAIL TRUE
        LABELS "starter-negative"
)
