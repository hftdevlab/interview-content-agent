cmake_minimum_required(VERSION 3.20)
project(quant_dev_interview_practice LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(CTest)
enable_testing()
find_package(Threads REQUIRED)

option(PRACTICE_ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(PRACTICE_ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(PRACTICE_ENABLE_TSAN "Enable ThreadSanitizer" OFF)

if(PRACTICE_ENABLE_TSAN AND (PRACTICE_ENABLE_ASAN OR PRACTICE_ENABLE_UBSAN))
    message(FATAL_ERROR "ThreadSanitizer must use a separate build from ASan/UBSan")
endif()

function(practice_configure_target target)
    target_compile_features(${target} PUBLIC cxx_std_20)

    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_compile_options(${target} PRIVATE
            -Wall
            -Wextra
            -Wpedantic
            -Wconversion
            -Wsign-conversion
        )

        set(sanitizers "")
        if(PRACTICE_ENABLE_ASAN)
            list(APPEND sanitizers "address")
        endif()
        if(PRACTICE_ENABLE_UBSAN)
            list(APPEND sanitizers "undefined")
        endif()
        if(PRACTICE_ENABLE_TSAN)
            list(APPEND sanitizers "thread")
        endif()

        if(sanitizers)
            list(JOIN sanitizers "," sanitizer_flags)
            target_compile_options(${target} PRIVATE
                -fsanitize=${sanitizer_flags}
                -fno-omit-frame-pointer
            )
            target_link_options(${target} PRIVATE
                -fsanitize=${sanitizer_flags}
                -fno-omit-frame-pointer
            )
        endif()
    endif()
endfunction()

add_subdirectory(questions/code-multi-source-stream-merger)
add_subdirectory(questions/fund-sequence-lock)
