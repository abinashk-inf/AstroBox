/*********************************
* Code by Kanishka Mohan Madhuni *
**********************************/

var UtilityView = Backbone.View.extend({
  el: '#utility-view',
  events: {
    "click .utility-button": "getButtonName"
  },
  initialize: function() {},
	onShow: function() {},

  /*
    Added new functionality to check which subview is clicked
  */
  getButtonName: function(e) {
    var el = $(e.currentTarget);
    var className = el.find('.control-link').attr('class').substring(13);
    ControlView.prototype.buttonName = className;
  }
});  
