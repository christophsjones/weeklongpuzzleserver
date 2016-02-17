  function showPs() {
    /* $('#p1').fadeIn(600);
    $('#p2').fadeIn(600);
    $('#p3').fadeIn(600);
    $('#p4').fadeIn(600); */
    $('p').first().fadeIn(500, function showNext() {
      $(this).next('p').fadeIn(400, showNext);
    });
  }

  $(document).ready(showPs);
