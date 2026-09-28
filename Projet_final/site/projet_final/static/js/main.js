$(function () {
  var tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
);

var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

$(".banner-slider").owlCarousel({
    responsiveClass: true,
    loop: false,
    margin: 0,
    autoplay: true,
    dots: false,
    nav: true,
    responsive: {
        0: {
            items: 1,
        },
        600: {
            items: 1,

        },
        1000: {
            items: 1,
        },
    }
});

$(".category-slider").owlCarousel({
    responsiveClass: true,
    loop: true,
    margin: 20,
    autoplay: true,
    dots: false,
    nav: true,
    responsive: {
        0: {
            items: 3,
        },
        600: {
            items: 3,

        },
        1000: {
            items: 4,
        },
        1200: {
            nav: true,
            items: 6,
        },
    }
});

$(".product-slider").owlCarousel({
    responsiveClass: true,
    autoplay: true,
    dots: false,
    responsive: {
        0: {
            nav: false,
            items: 2,
        },
        600: {
            nav: true,
            items: 2,

        },
        1000: {
            nav: true,
            items: 3,
        },
        1200: {
            nav: true,
            items: 4,
        },
    }
});



$(".blog-slider").owlCarousel({
    responsiveClass: true,
    loop: false,
    margin: 40,
    autoplay: false,
    responsive: {
        0: {
            nav: false,
            dots: true,
            items: 1,
        },
        600: {
            nav: false,
            dots: false,
            items: 2,

        },
        1000: {
            nav: true,
            dots: false,
            items: 3,
        },
    }
});

/////// Nice Select ///
$(".nice-option").niceSelect();

//// Price Range ///

var slider = document.getElementById('priceRange');
var priceRangeValue = document.getElementById('priceRange-value');

// Check if the elements exist
if (slider && priceRangeValue) {
    // Your code for creating the slider and updating the input field
    noUiSlider.create(slider, {
        start: [20, 80],
        connect: true,
        range: {
            'min': 0,
            'max': 100
        },
        format: {
            to: function (value) {
                return Math.round(value);
            },
            from: function (value) {
                return value.replace('$', '');
            }
        }
    });

    // Update input field with slider value
    slider.noUiSlider.on('update', function (values, handle) {
        priceRangeValue.textContent = '$' + values[0] + ' - $' + values[1];
    });
}


// if ($('#product-img-zoom').length > 0) {
//     ZoomActive();
// }

// function ZoomActive() {
//     $('#product-img-zoom').ezPlus({
//         zoomType: 'inner',
//         cursor: 'crosshair',
//         borderSize: 0
//     });
// }

var $sliderSingle = initSlider();

    // Initialize the slider
    function initSlider() {
        if ($(".slider-nav").length > 0) {
            var $sliderSingle = $(".slider-nav").slick({
                slidesToShow: 4,
                slidesToScroll: 1,
                arrows: false,
                dots: false,
                focusOnSelect: true
            });
            return $sliderSingle;
        }
        return null;
    }

    // Function to get the index of the active slide
    function getActiveSlideIndex() {
        if ($sliderSingle) {
            return $sliderSingle.slick('slickCurrentSlide');
        }
        return -1;
    }

    // Function to get the image source of the active slide
    function getImageOfActiveSlide() {
        var activeSlideIndex = getActiveSlideIndex();
        if (activeSlideIndex !== -1) {
            var $activeSlide = $(".slider-nav .slick-slide").eq(activeSlideIndex);
            var $img = $activeSlide.find('img');
            var imgSrc = $img.attr('src');
            return imgSrc;
        }
        return null;
    }

    // Function to update the active image and zoom
    function updateActiveImage() {
        var activeImgSrc = getImageOfActiveSlide();
        if (activeImgSrc && $('#product-img-active').length > 0) {
            $('#product-img-active img').attr('src', activeImgSrc);
        }
    }

    // Event listener for slider change
    if ($sliderSingle) {
        $sliderSingle.on('afterChange', function (event, slick, currentSlide) {
            updateActiveImage();
        });
    }


      //////  Counter Increament

  $(".count-increament").click(function (e) {
    var count = $(this).parent().find("input").val();
    count++;
    $(this).parent().find("input").val(count);
  });

  //////  Counter Decreament

  $(".count-decreament").click(function (e) {
    var count = $(this).parent().find("input").val();
    count--;
    if (count > 0) {
      $(this).parent().find("input").val(count);
    }
  });

});
