/* Standalone stdint.h for glog/fmt on iOS 26.2 SDK (module-system bypass).
   Uses Clang built-in predefined macros — no SDK modules required. */
#pragma once
#ifndef _STDINT_H_
#define _STDINT_H_

typedef __INT8_TYPE__   int8_t;
typedef __INT16_TYPE__  int16_t;
typedef __INT32_TYPE__  int32_t;
typedef __INT64_TYPE__  int64_t;
typedef __UINT8_TYPE__  uint8_t;
typedef __UINT16_TYPE__ uint16_t;
typedef __UINT32_TYPE__ uint32_t;
typedef __UINT64_TYPE__ uint64_t;
typedef __INTPTR_TYPE__   intptr_t;
typedef __UINTPTR_TYPE__  uintptr_t;
typedef __PTRDIFF_TYPE__  ptrdiff_t;
typedef __SIZE_TYPE__     size_t;
typedef long long         intmax_t;
typedef unsigned long long uintmax_t;

typedef int8_t   int_least8_t;
typedef int16_t  int_least16_t;
typedef int32_t  int_least32_t;
typedef int64_t  int_least64_t;
typedef uint8_t  uint_least8_t;
typedef uint16_t uint_least16_t;
typedef uint32_t uint_least32_t;
typedef uint64_t uint_least64_t;

typedef int8_t   int_fast8_t;
typedef int16_t  int_fast16_t;
typedef int32_t  int_fast32_t;
typedef int64_t  int_fast64_t;
typedef uint8_t  uint_fast8_t;
typedef uint16_t uint_fast16_t;
typedef uint32_t uint_fast32_t;
typedef uint64_t uint_fast64_t;

#ifndef INT8_MAX
# define INT8_MIN    (-128)
# define INT8_MAX    127
# define INT16_MIN   (-32768)
# define INT16_MAX   32767
# define INT32_MIN   (-2147483647-1)
# define INT32_MAX   2147483647
# define INT64_MIN   (-9223372036854775807LL-1LL)
# define INT64_MAX   9223372036854775807LL
# define UINT8_MAX   255
# define UINT16_MAX  65535
# define UINT32_MAX  4294967295U
# define UINT64_MAX  18446744073709551615ULL
# define SIZE_MAX    __SIZE_MAX__
#endif

#define INT8_C(v)    (v)
#define INT16_C(v)   (v)
#define INT32_C(v)   (v)
#define INT64_C(v)   (v ## LL)
#define UINT8_C(v)   (v)
#define UINT16_C(v)  (v)
#define UINT32_C(v)  (v ## U)
#define UINT64_C(v)  (v ## ULL)
#define INTMAX_C(v)  (v ## LL)
#define UINTMAX_C(v) (v ## ULL)

#endif /* _STDINT_H_ */
